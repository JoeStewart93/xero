package protocol

import (
	"bytes"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

type vectorFile struct {
	Vectors []vector `json:"vectors"`
}

type vector struct {
	FrameB64          string         `json:"frame_b64"`
	MessageType       string         `json:"message_type"`
	NonceHex          string         `json:"nonce_hex"`
	Payload           map[string]any `json:"payload"`
	PeerPublicKeyB64  string         `json:"peer_public_key_b64"`
	PrivateKeyB64     string         `json:"private_key_b64"`
	SessionID          string         `json:"session_id"`
	SessionIDHex       string         `json:"session_id_hex"`
}

func loadVectors(t *testing.T) []vector {
	t.Helper()
	path := filepath.Join("..", "testdata", "vectors.json")
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var fixture vectorFile
	if err := json.Unmarshal(content, &fixture); err != nil {
		t.Fatal(err)
	}
	return fixture.Vectors
}

func mustDecodeB64(t *testing.T, value string) []byte {
	t.Helper()
	decoded, err := base64.StdEncoding.DecodeString(value)
	if err != nil {
		t.Fatal(err)
	}
	return decoded
}

func mustDecodeHex(t *testing.T, value string) []byte {
	t.Helper()
	decoded, err := hex.DecodeString(strings.ReplaceAll(value, "-", ""))
	if err != nil {
		t.Fatal(err)
	}
	return decoded
}

func TestEncodeMatchesPythonVectors(t *testing.T) {
	for _, item := range loadVectors(t) {
		t.Run(item.MessageType, func(t *testing.T) {
			frame, err := Encode(
				mustDecodeB64(t, item.PrivateKeyB64),
				mustDecodeB64(t, item.PeerPublicKeyB64),
				item.MessageType,
				item.Payload,
				mustDecodeHex(t, item.SessionIDHex),
				mustDecodeHex(t, item.NonceHex),
			)
			if err != nil {
				t.Fatal(err)
			}
			expected := mustDecodeB64(t, item.FrameB64)
			if !bytes.Equal(frame, expected) {
				t.Fatalf("Go frame did not match Python vector for %s", item.MessageType)
			}
		})
	}
}

func TestDecodePythonVectors(t *testing.T) {
	for _, item := range loadVectors(t) {
		t.Run(item.MessageType, func(t *testing.T) {
			decoded, err := Decode(mustDecodeB64(t, item.FrameB64), mustDecodeB64(t, "AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA="))
			if err != nil {
				t.Fatal(err)
			}
			if decoded.MessageType != item.MessageType {
				t.Fatalf("message type mismatch: %s != %s", decoded.MessageType, item.MessageType)
			}
			if !bytes.Equal(decoded.SessionID, mustDecodeHex(t, item.SessionIDHex)) {
				t.Fatal("session id mismatch")
			}
		})
	}
}

func TestTamperedPythonVectorRejected(t *testing.T) {
	item := loadVectors(t)[0]
	frame := mustDecodeB64(t, item.FrameB64)
	frame[len(frame)-1] ^= 0x01
	if _, err := Decode(frame, mustDecodeB64(t, "AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA=")); err == nil {
		t.Fatal("expected tampered vector to be rejected")
	}
}
