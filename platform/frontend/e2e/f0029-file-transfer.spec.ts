import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';

import { expect, test } from '@playwright/test';

import { baseURL, c2IsAvailable, c2Token, getProtocolInfo, loginAndConnectC2, websocketUrl } from './support/c2';
import { createProtocolFixture } from './support/protocolFrame';
import type { DecodedProtocolFrame, JsonValue, ProtocolFixture } from './support/protocolFrame';

async function waitForSocketOpen(socket: WebSocket) {
  if (socket.readyState === WebSocket.OPEN) {
    return;
  }
  await new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Beacon WebSocket did not open')), 10_000);
    socket.addEventListener(
      'open',
      () => {
        clearTimeout(timer);
        resolve();
      },
      { once: true },
    );
    socket.addEventListener(
      'error',
      () => {
        clearTimeout(timer);
        reject(new Error('Beacon WebSocket failed to open'));
      },
      { once: true },
    );
  });
}

async function socketMessageBuffer(event: MessageEvent): Promise<Buffer> {
  if (event.data instanceof Blob) {
    return Buffer.from(await event.data.arrayBuffer());
  }
  if (event.data instanceof ArrayBuffer) {
    return Buffer.from(event.data);
  }
  return Buffer.from(event.data);
}

async function waitForFrame(
  socket: WebSocket,
  fixture: ProtocolFixture,
  predicate: (frame: DecodedProtocolFrame) => boolean,
) {
  return new Promise<DecodedProtocolFrame>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Expected protocol frame was not received')), 15_000);
    const onMessage = async (event: MessageEvent) => {
      try {
        const decoded = await fixture.decode(await socketMessageBuffer(event));
        if (!predicate(decoded)) {
          return;
        }
        clearTimeout(timer);
        socket.removeEventListener('message', onMessage);
        resolve(decoded);
      } catch {
        // Ignore unrelated frames in this helper and keep waiting for the target frame.
      }
    };
    socket.addEventListener('message', onMessage);
    socket.addEventListener(
      'close',
      () => {
        clearTimeout(timer);
        reject(new Error('Beacon WebSocket closed before expected frame'));
      },
      { once: true },
    );
  });
}

async function sendSessionFrame(socket: WebSocket, fixture: ProtocolFixture, payload: Record<string, JsonValue>) {
  socket.send(await fixture.encode('SESSION_DATA', payload));
}

test('F0029 uploads and downloads files through live C2 file-browser transfer frames', async ({ page }) => {
  test.setTimeout(90_000);
  test.skip(!(await c2IsAvailable()), 'C2 backend stack is not available');

  const eventId = Date.now();
  const hostname = `f0029-transfer-${eventId}`;
  const fileBytes = Buffer.from('f0029 live transfer payload');
  const downloadBytes = Buffer.from('f0029 beacon source download payload');
  const downloadHash = createHash('sha256').update(downloadBytes).digest('hex');
  let uploadedBytes = Buffer.alloc(0);

  await loginAndConnectC2(page);
  const accessToken = await c2Token();
  const protocol = await getProtocolInfo(accessToken);
  const fixture = await createProtocolFixture(protocol);

  const socket = new WebSocket(websocketUrl('/ws/beacon'), ['xero.beacon.v1']);
  await waitForSocketOpen(socket);
  socket.send(
    await fixture.encode('REGISTER', {
      architecture: 'x64',
      external_ip: '198.51.100.129',
      hostname,
      internal_ip: '10.129.0.10',
      machine_fingerprint_hash: `playwright-f0029-${eventId}`,
      os: 'Windows 11',
      pid: 2929,
      supported_versions: [1],
    }),
  );
  const registered = await waitForFrame(socket, fixture, (frame) => frame.messageType === 'ACK');
  const beaconId = String(registered.payload.beacon_id);

  await page.goto(`${baseURL}/beacons`);
  await page.getByLabel('Search beacons').fill(hostname);
  await expect(page.getByTestId('beacon-roster')).toContainText(hostname, { timeout: 10_000 });
  await page.getByTestId(`beacon-row-${beaconId}`).dblclick();
  await page.getByRole('button', { name: /Files/ }).click();
  await page.getByRole('button', { name: 'Open' }).click();

  const openFrame = await waitForFrame(
    socket,
    fixture,
    (frame) => frame.messageType === 'SESSION_DATA' && frame.payload.op === 'open',
  );
  const sessionId = String(openFrame.payload.session_id);
  await sendSessionFrame(socket, fixture, {
    beacon_id: beaconId,
    op: 'open_ack',
    root_path: '/',
    session_id: sessionId,
    session_type: 'file_browser',
  });

  const listFrame = await waitForFrame(
    socket,
    fixture,
    (frame) => frame.messageType === 'SESSION_DATA' && frame.payload.op === 'list_dir',
  );
  await sendSessionFrame(socket, fixture, {
    beacon_id: beaconId,
    entries: [],
    ok: true,
    op: 'list_dir',
    path: '',
    request_id: listFrame.payload.request_id,
    session_id: sessionId,
    session_type: 'file_browser',
  });

  await page.locator('input[type="file"]').setInputFiles({
    buffer: fileBytes,
    mimeType: 'application/octet-stream',
    name: 'f0029-upload.bin',
  });

  const uploadInit = await waitForFrame(
    socket,
    fixture,
    (frame) => frame.messageType === 'SESSION_DATA' && frame.payload.op === 'upload_init',
  );
  const transferId = String(uploadInit.payload.transfer_id);
  await sendSessionFrame(socket, fixture, {
    beacon_id: beaconId,
    next_sequence: 0,
    ok: true,
    op: 'upload_ready',
    received_sequences: [],
    request_id: uploadInit.payload.request_id,
    session_id: sessionId,
    session_type: 'file_browser',
    transfer_id: transferId,
  });

  const uploadChunk = await waitForFrame(
    socket,
    fixture,
    (frame) => frame.messageType === 'SESSION_DATA' && frame.payload.op === 'upload_chunk',
  );
  uploadedBytes = Buffer.concat([uploadedBytes, Buffer.from(String(uploadChunk.payload.data_b64), 'base64')]);
  await sendSessionFrame(socket, fixture, {
    beacon_id: beaconId,
    ok: true,
    op: 'upload_ack',
    request_id: uploadChunk.payload.request_id,
    sequence: uploadChunk.payload.sequence,
    session_id: sessionId,
    session_type: 'file_browser',
    transfer_id: transferId,
  });

  const uploadComplete = await waitForFrame(
    socket,
    fixture,
    (frame) => frame.messageType === 'SESSION_DATA' && frame.payload.op === 'upload_complete',
  );
  await sendSessionFrame(socket, fixture, {
    beacon_id: beaconId,
    ok: true,
    op: 'upload_complete',
    request_id: uploadComplete.payload.request_id,
    session_id: sessionId,
    session_type: 'file_browser',
    sha256: createHash('sha256').update(uploadedBytes).digest('hex'),
    transfer_id: transferId,
  });

  await expect(page.getByTestId('file-transfer-progress')).toContainText('100%', { timeout: 10_000 });
  expect(uploadedBytes.equals(fileBytes)).toBeTruthy();

  const refreshAfterUpload = await waitForFrame(
    socket,
    fixture,
    (frame) => frame.messageType === 'SESSION_DATA' && frame.payload.op === 'list_dir',
  );
  await sendSessionFrame(socket, fixture, {
    beacon_id: beaconId,
    entries: [
      {
        modified_at: new Date().toISOString(),
        name: 'beacon-download.bin',
        path: 'beacon-download.bin',
        permissions: '-rw-r--r--',
        size: downloadBytes.length,
        type: 'file',
      },
    ],
    ok: true,
    op: 'list_dir',
    path: '',
    request_id: refreshAfterUpload.payload.request_id,
    session_id: sessionId,
    session_type: 'file_browser',
  });

  await expect(page.getByRole('button', { name: 'Download beacon-download.bin' })).toBeVisible();
  const browserDownload = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download beacon-download.bin' }).click();

  const downloadInit = await waitForFrame(
    socket,
    fixture,
    (frame) => frame.messageType === 'SESSION_DATA' && frame.payload.op === 'download_init',
  );
  const downloadTransferId = String(downloadInit.payload.transfer_id);
  await sendSessionFrame(socket, fixture, {
    beacon_id: beaconId,
    chunk_size_bytes: downloadBytes.length,
    ok: true,
    op: 'download_ready',
    path: 'beacon-download.bin',
    request_id: downloadInit.payload.request_id,
    session_id: sessionId,
    session_type: 'file_browser',
    sha256: downloadHash,
    size_bytes: downloadBytes.length,
    total_chunks: 1,
    transfer_id: downloadTransferId,
  });

  const downloadChunk = await waitForFrame(
    socket,
    fixture,
    (frame) => frame.messageType === 'SESSION_DATA' && frame.payload.op === 'download_chunk_request',
  );
  await sendSessionFrame(socket, fixture, {
    beacon_id: beaconId,
    chunk_sha256: downloadHash,
    data_b64: downloadBytes.toString('base64'),
    ok: true,
    op: 'download_chunk',
    request_id: downloadChunk.payload.request_id,
    sequence: downloadChunk.payload.sequence,
    session_id: sessionId,
    session_type: 'file_browser',
    transfer_id: downloadTransferId,
  });

  const downloaded = await browserDownload;
  const downloadedPath = await downloaded.path();
  expect(downloaded.suggestedFilename()).toBe('beacon-download.bin');
  expect(downloadedPath).toBeTruthy();
  const savedBytes = await readFile(downloadedPath as string);
  expect(createHash('sha256').update(savedBytes).digest('hex')).toBe(downloadHash);
  await expect(page.getByTestId('file-transfer-progress')).toContainText('Download complete');
  socket.close(1000);
});
