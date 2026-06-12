package protocol

import (
	"bytes"
	"crypto/aes"
	"crypto/cipher"
	"crypto/ecdh"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"io"
)

const (
	Magic             = "XERO"
	Version           = byte(1)
	FrameHeaderLength = 72
	FrameHMACLength   = 32
)

var messageValues = map[string]byte{
	"REGISTER":       1,
	"HEARTBEAT":      2,
	"TASK_POLL":      3,
	"TASK_RESULT":    4,
	"SESSION_DATA":   5,
	"ACK":            6,
	"PROTOCOL_ERROR": 7,
}

var messageNames = map[byte]string{
	1: "REGISTER",
	2: "HEARTBEAT",
	3: "TASK_POLL",
	4: "TASK_RESULT",
	5: "SESSION_DATA",
	6: "ACK",
	7: "PROTOCOL_ERROR",
}

type DecodedFrame struct {
	Version     byte
	MessageType string
	SessionID   []byte
	Nonce       []byte
	PublicKey   []byte
	Payload     map[string]any
}

func PublicKey(privateKeyRaw []byte) ([]byte, error) {
	privateKey, err := ecdh.X25519().NewPrivateKey(privateKeyRaw)
	if err != nil {
		return nil, err
	}
	return privateKey.PublicKey().Bytes(), nil
}

func Encode(
	privateKeyRaw []byte,
	peerPublicKeyRaw []byte,
	messageType string,
	payload map[string]any,
	sessionID []byte,
	nonce []byte,
) ([]byte, error) {
	if len(sessionID) != 16 {
		return nil, errors.New("session id must be 16 bytes")
	}
	if len(nonce) != 12 {
		return nil, errors.New("nonce must be 12 bytes")
	}
	messageValue, ok := messageValues[messageType]
	if !ok {
		return nil, fmt.Errorf("unknown message type %s", messageType)
	}
	payloadBytes, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}
	keys, senderPublicKey, err := deriveKeys(privateKeyRaw, peerPublicKeyRaw, sessionID)
	if err != nil {
		return nil, err
	}
	block, err := aes.NewCipher(keys.encryptionKey)
	if err != nil {
		return nil, err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, err
	}
	encryptedPayload := gcm.Seal(nil, nonce, payloadBytes, sessionID)
	header := make([]byte, FrameHeaderLength)
	copy(header[0:4], []byte(Magic))
	header[4] = Version
	header[5] = messageValue
	header[6] = 0
	header[7] = FrameHeaderLength
	binary.BigEndian.PutUint32(header[8:12], uint32(len(encryptedPayload)))
	copy(header[12:28], sessionID)
	copy(header[28:40], nonce)
	copy(header[40:72], senderPublicKey)
	frameWithoutHMAC := append(header, encryptedPayload...)
	signature := hmac.New(sha256.New, keys.hmacKey)
	signature.Write(frameWithoutHMAC)
	return append(frameWithoutHMAC, signature.Sum(nil)...), nil
}

func Decode(frame []byte, privateKeyRaw []byte) (*DecodedFrame, error) {
	if len(frame) < FrameHeaderLength+16+FrameHMACLength {
		return nil, errors.New("malformed frame")
	}
	if string(frame[0:4]) != Magic {
		return nil, errors.New("invalid magic")
	}
	version := frame[4]
	if version != Version {
		return nil, fmt.Errorf("unsupported version %d", version)
	}
	messageType, ok := messageNames[frame[5]]
	if !ok {
		return nil, fmt.Errorf("unknown message type %d", frame[5])
	}
	headerLength := int(frame[7])
	if headerLength != FrameHeaderLength {
		return nil, errors.New("invalid header length")
	}
	payloadLength := int(binary.BigEndian.Uint32(frame[8:12]))
	expectedLength := FrameHeaderLength + payloadLength + FrameHMACLength
	if len(frame) != expectedLength {
		return nil, errors.New("payload length mismatch")
	}
	sessionID := bytes.Clone(frame[12:28])
	nonce := bytes.Clone(frame[28:40])
	senderPublicKey := bytes.Clone(frame[40:72])
	keys, _, err := deriveKeys(privateKeyRaw, senderPublicKey, sessionID)
	if err != nil {
		return nil, err
	}
	receivedHMAC := frame[FrameHeaderLength+payloadLength:]
	expectedHMAC := hmac.New(sha256.New, keys.hmacKey)
	expectedHMAC.Write(frame[:FrameHeaderLength+payloadLength])
	if !hmac.Equal(receivedHMAC, expectedHMAC.Sum(nil)) {
		return nil, errors.New("hmac mismatch")
	}
	block, err := aes.NewCipher(keys.encryptionKey)
	if err != nil {
		return nil, err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, err
	}
	payloadBytes, err := gcm.Open(nil, nonce, frame[FrameHeaderLength:FrameHeaderLength+payloadLength], sessionID)
	if err != nil {
		return nil, err
	}
	var payload map[string]any
	if err := json.Unmarshal(payloadBytes, &payload); err != nil {
		return nil, err
	}
	return &DecodedFrame{
		Version:     version,
		MessageType: messageType,
		SessionID:   sessionID,
		Nonce:       nonce,
		PublicKey:   senderPublicKey,
		Payload:     payload,
	}, nil
}

type sessionKeys struct {
	encryptionKey []byte
	hmacKey       []byte
}

func deriveKeys(privateKeyRaw []byte, peerPublicKeyRaw []byte, sessionID []byte) (*sessionKeys, []byte, error) {
	privateKey, err := ecdh.X25519().NewPrivateKey(privateKeyRaw)
	if err != nil {
		return nil, nil, err
	}
	peerPublicKey, err := ecdh.X25519().NewPublicKey(peerPublicKeyRaw)
	if err != nil {
		return nil, nil, err
	}
	sharedSecret, err := privateKey.ECDH(peerPublicKey)
	if err != nil {
		return nil, nil, err
	}
	derived, err := hkdfSHA256(sharedSecret, sessionID, []byte("xero-protocol-v1"), 64)
	if err != nil {
		return nil, nil, err
	}
	return &sessionKeys{encryptionKey: derived[:32], hmacKey: derived[32:]}, privateKey.PublicKey().Bytes(), nil
}

func hkdfSHA256(secret []byte, salt []byte, info []byte, length int) ([]byte, error) {
	if len(salt) == 0 {
		salt = make([]byte, sha256.Size)
	}
	extract := hmac.New(sha256.New, salt)
	extract.Write(secret)
	prk := extract.Sum(nil)
	output := make([]byte, 0, length)
	var previous []byte
	for counter := byte(1); len(output) < length; counter++ {
		expand := hmac.New(sha256.New, prk)
		expand.Write(previous)
		expand.Write(info)
		expand.Write([]byte{counter})
		previous = expand.Sum(nil)
		output = append(output, previous...)
		if counter == 255 {
			break
		}
	}
	if len(output) < length {
		return nil, io.ErrShortBuffer
	}
	return output[:length], nil
}
