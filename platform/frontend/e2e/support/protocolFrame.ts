import { createCipheriv, createDecipheriv, createHmac, hkdfSync, randomBytes, randomUUID, timingSafeEqual, webcrypto } from 'node:crypto';

const frameHeaderLength = 72;

const messageTypes = {
  ACK: 6,
  HEARTBEAT: 2,
  PROTOCOL_ERROR: 7,
  REGISTER: 1,
  SESSION_DATA: 5,
  TASK_POLL: 3,
  TASK_RESULT: 4,
} as const;

const messageNames: Record<number, ProtocolMessageType> = {
  1: 'REGISTER',
  2: 'HEARTBEAT',
  3: 'TASK_POLL',
  4: 'TASK_RESULT',
  5: 'SESSION_DATA',
  6: 'ACK',
  7: 'PROTOCOL_ERROR',
};

export type JsonValue = boolean | null | number | string | JsonValue[] | { [key: string]: JsonValue };
export type ProtocolMessageType = keyof typeof messageTypes;

export interface ProtocolInfo {
  c2_public_key_b64: string;
  current_version: number;
  frame_harness_enabled?: boolean;
}

export interface DecodedProtocolFrame {
  messageType: ProtocolMessageType;
  payload: Record<string, JsonValue>;
}

export interface ProtocolFixture {
  decode(frame: Buffer): Promise<DecodedProtocolFrame>;
  encode(messageType: ProtocolMessageType, payload: Record<string, JsonValue>): Promise<Buffer>;
}

function canonicalize(value: JsonValue): JsonValue {
  if (Array.isArray(value)) {
    return value.map((item) => canonicalize(item));
  }
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonicalize(value[key])]));
  }
  return value;
}

function uuidBytes(value: string): Buffer {
  return Buffer.from(value.replaceAll('-', ''), 'hex');
}

export async function encodeProtocolFrame(
  protocol: ProtocolInfo,
  messageType: ProtocolMessageType,
  payload: Record<string, JsonValue>,
) {
  const fixture = await createProtocolFixture(protocol);
  return fixture.encode(messageType, payload);
}

export async function createProtocolFixture(protocol: ProtocolInfo): Promise<ProtocolFixture> {
  const keyPair = await webcrypto.subtle.generateKey({ name: 'X25519' }, true, ['deriveBits']);
  const senderPublicKey = Buffer.from(await webcrypto.subtle.exportKey('raw', keyPair.publicKey));

  async function deriveKeys(peerPublicKeyBytes: Buffer, sessionId: Buffer) {
    const peerPublicKey = await webcrypto.subtle.importKey('raw', peerPublicKeyBytes, { name: 'X25519' }, false, []);
    const sharedSecret = Buffer.from(await webcrypto.subtle.deriveBits({ name: 'X25519', public: peerPublicKey }, keyPair.privateKey, 256));
    const derived = Buffer.from(hkdfSync('sha256', sharedSecret, sessionId, Buffer.from('xero-protocol-v1'), 64));
    return {
      encryptionKey: derived.subarray(0, 32),
      hmacKey: derived.subarray(32),
    };
  }

  return {
    async decode(frame: Buffer): Promise<DecodedProtocolFrame> {
      if (frame.length < frameHeaderLength + 16 + 32) {
        throw new Error('Protocol frame is too short');
      }
      if (frame.subarray(0, 4).toString('ascii') !== 'XERO') {
        throw new Error('Protocol frame magic is invalid');
      }
      const messageType = messageNames[frame[5]];
      if (!messageType) {
        throw new Error(`Unknown protocol message type ${frame[5]}`);
      }
      const payloadLength = frame.readUInt32BE(8);
      const expectedLength = frameHeaderLength + payloadLength + 32;
      if (frame.length !== expectedLength) {
        throw new Error('Protocol frame payload length is invalid');
      }
      const sessionId = frame.subarray(12, 28);
      const nonce = frame.subarray(28, 40);
      const peerPublicKey = frame.subarray(40, 72);
      const encryptedPayload = frame.subarray(frameHeaderLength, frameHeaderLength + payloadLength);
      const receivedHmac = frame.subarray(frameHeaderLength + payloadLength);
      const keys = await deriveKeys(peerPublicKey, sessionId);
      const expectedHmac = createHmac('sha256', keys.hmacKey).update(frame.subarray(0, frameHeaderLength + payloadLength)).digest();
      if (!timingSafeEqual(receivedHmac, expectedHmac)) {
        throw new Error('Protocol frame HMAC is invalid');
      }
      const ciphertext = encryptedPayload.subarray(0, encryptedPayload.length - 16);
      const tag = encryptedPayload.subarray(encryptedPayload.length - 16);
      const decipher = createDecipheriv('aes-256-gcm', keys.encryptionKey, nonce);
      decipher.setAAD(sessionId);
      decipher.setAuthTag(tag);
      const payloadBytes = Buffer.concat([decipher.update(ciphertext), decipher.final()]);
      const payload = JSON.parse(payloadBytes.toString('utf8')) as Record<string, JsonValue>;
      return { messageType, payload };
    },

    async encode(messageType: ProtocolMessageType, payload: Record<string, JsonValue>) {
      const sessionId = uuidBytes(randomUUID());
      const nonce = randomBytes(12);
      const keys = await deriveKeys(Buffer.from(protocol.c2_public_key_b64, 'base64'), sessionId);
      const payloadBytes = Buffer.from(JSON.stringify(canonicalize(payload)));
      const cipher = createCipheriv('aes-256-gcm', keys.encryptionKey, nonce);
      cipher.setAAD(sessionId);
      const encryptedPayload = Buffer.concat([cipher.update(payloadBytes), cipher.final(), cipher.getAuthTag()]);
      const header = Buffer.alloc(frameHeaderLength);
      header.write('XERO', 0, 'ascii');
      header[4] = 1;
      header[5] = messageTypes[messageType];
      header[6] = 0;
      header[7] = frameHeaderLength;
      header.writeUInt32BE(encryptedPayload.length, 8);
      sessionId.copy(header, 12);
      nonce.copy(header, 28);
      senderPublicKey.copy(header, 40);
      const frameWithoutHmac = Buffer.concat([header, encryptedPayload]);
      const frameHmac = createHmac('sha256', keys.hmacKey).update(frameWithoutHmac).digest();
      return Buffer.concat([frameWithoutHmac, frameHmac]);
    },
  };
}
