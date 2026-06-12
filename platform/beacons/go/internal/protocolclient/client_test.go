package protocolclient

import (
	"crypto/rand"
	"encoding/base64"
	"testing"

	xeroprotocol "xero-protocol"
)

func TestProtocolClientEncodeDecodeWithPeer(t *testing.T) {
	serverPrivate := make([]byte, 32)
	if _, err := rand.Read(serverPrivate); err != nil {
		t.Fatal(err)
	}
	serverPublic, err := xeroprotocol.PublicKey(serverPrivate)
	if err != nil {
		t.Fatal(err)
	}
	client, err := New(base64.StdEncoding.EncodeToString(serverPublic))
	if err != nil {
		t.Fatal(err)
	}
	frame, err := client.Encode("HEARTBEAT", map[string]any{"beacon_id": "beacon-one"})
	if err != nil {
		t.Fatal(err)
	}
	decoded, err := xeroprotocol.Decode(frame, serverPrivate)
	if err != nil {
		t.Fatal(err)
	}
	if decoded.MessageType != "HEARTBEAT" || decoded.Payload["beacon_id"] != "beacon-one" {
		t.Fatalf("unexpected decoded frame: %#v", decoded)
	}
}
