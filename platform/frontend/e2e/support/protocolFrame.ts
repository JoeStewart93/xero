import { createCipheriv, createHmac, hkdfSync, randomBytes, randomUUID, webcrypto } from 'node:crypto';

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

export type JsonValue = boolean | null | number | string | JsonValue[] | { [key: string]: JsonValue };
export type ProtocolMessageType = keyof typeof messageTypes;

export interface ProtocolInfo {
  c2_public_key_b64: string;
  current_version: number;
  frame_harness_enabled?: boolean;
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
  const keyPair = await webcrypto.subtle.generateKey({ name: 'X25519' }, true, ['deriveBits']);
  const c2PublicKey = await webcrypto.subtle.importKey(
    'raw',
    Buffer.from(protocol.c2_public_key_b64, 'base64'),
    { name: 'X25519' },
    false,
    [],
  );
  const sharedSecret = Buffer.from(await webcrypto.subtle.deriveBits({ name: 'X25519', public: c2PublicKey }, keyPair.privateKey, 256));
  const sessionId = uuidBytes(randomUUID());
  const nonce = randomBytes(12);
  const derived = Buffer.from(hkdfSync('sha256', sharedSecret, sessionId, Buffer.from('xero-protocol-v1'), 64));
  const encryptionKey = derived.subarray(0, 32);
  const hmacKey = derived.subarray(32);
  const payloadBytes = Buffer.from(JSON.stringify(canonicalize(payload)));
  const cipher = createCipheriv('aes-256-gcm', encryptionKey, nonce);
  cipher.setAAD(sessionId);
  const encryptedPayload = Buffer.concat([cipher.update(payloadBytes), cipher.final(), cipher.getAuthTag()]);
  const senderPublicKey = Buffer.from(await webcrypto.subtle.exportKey('raw', keyPair.publicKey));
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
  const frameHmac = createHmac('sha256', hmacKey).update(frameWithoutHmac).digest();
  return Buffer.concat([frameWithoutHmac, frameHmac]);
}
