package protocolclient

import (
	"crypto/rand"
	"encoding/base64"
	"fmt"

	xeroprotocol "xero-protocol"
)

type Client struct {
	privateKey []byte
	peerKey    []byte
	sessionID  []byte
}

func New(c2PublicKeyB64 string) (*Client, error) {
	peerKey, err := base64.StdEncoding.DecodeString(c2PublicKeyB64)
	if err != nil {
		return nil, err
	}
	privateKey := make([]byte, 32)
	sessionID := make([]byte, 16)
	if _, err := rand.Read(privateKey); err != nil {
		return nil, err
	}
	if _, err := rand.Read(sessionID); err != nil {
		return nil, err
	}
	return &Client{privateKey: privateKey, peerKey: peerKey, sessionID: sessionID}, nil
}

func (c *Client) Encode(messageType string, payload map[string]any) ([]byte, error) {
	nonce := make([]byte, 12)
	if _, err := rand.Read(nonce); err != nil {
		return nil, err
	}
	return xeroprotocol.Encode(c.privateKey, c.peerKey, messageType, payload, c.sessionID, nonce)
}

func (c *Client) Decode(frame []byte) (*xeroprotocol.DecodedFrame, error) {
	return xeroprotocol.Decode(frame, c.privateKey)
}

func (c *Client) SessionIDString() string {
	if len(c.sessionID) != 16 {
		return ""
	}
	return fmt.Sprintf(
		"%x-%x-%x-%x-%x",
		c.sessionID[0:4],
		c.sessionID[4:6],
		c.sessionID[6:8],
		c.sessionID[8:10],
		c.sessionID[10:16],
	)
}
