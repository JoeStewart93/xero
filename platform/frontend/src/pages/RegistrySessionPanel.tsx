import { useCallback, useEffect, useRef, useState } from 'react';
import { Database, Edit3, FolderKey, RefreshCw, Save, Trash2, X } from 'lucide-react';

import {
  closeRegistrySession,
  createRegistrySession,
} from '../api';
import type { Beacon, RegistrySession } from '../api';
import { ModalShell } from '../components/ModalShell';
import type { C2Connection } from '../c2ConnectionContext';
import { ShellSessionClient } from '../shellSessionClient';
import type { RegistryValueEntry, ShellSessionConnectionStatus, ShellSessionMessage } from '../shellSessionClient';

const registryHives = ['HKLM', 'HKCU', 'HKU', 'HKCR', 'HKCC'] as const;
type RegistryHive = (typeof registryHives)[number];
type RegistryValueType = 'REG_DWORD' | 'REG_SZ';

interface RegistrySessionPanelProps {
  beacon: Beacon;
  connection: C2Connection;
}

interface PendingRegistryAction {
  action: 'reg_delete_value' | 'reg_write_value';
  hive: RegistryHive;
  keyPath: string;
  requestId: string;
  value?: number | string;
  valueName: string;
  valueType?: RegistryValueType;
}

function isWindowsBeacon(beacon: Beacon): boolean {
  return beacon.os.toLowerCase().includes('windows');
}

function registryErrorMessage(message: ShellSessionMessage): string {
  if (message.message) {
    return message.message;
  }
  if (message.error_code) {
    return message.error_code.replace(/_/g, ' ');
  }
  return 'Registry operation failed.';
}

function registryValueDisplay(value: RegistryValueEntry): string {
  if (Array.isArray(value.value)) {
    return value.value.join(', ');
  }
  if (value.value === undefined || value.value === null) {
    return value.writable ? '(empty)' : 'Read-only type';
  }
  return String(value.value);
}

function joinRegistryPath(parent: string, child: string): string {
  return parent ? `${parent}\\${child}` : child;
}

export function RegistrySessionPanel({ beacon, connection }: RegistrySessionPanelProps) {
  const clientRef = useRef<ShellSessionClient | null>(null);
  const hasRequestedInitialKeyRef = useRef(false);
  const pendingActionRef = useRef<PendingRegistryAction | null>(null);
  const requestCounterRef = useRef(0);
  const [connectionStatus, setConnectionStatus] = useState<ShellSessionConnectionStatus>('disconnected');
  const [editorValue, setEditorValue] = useState('');
  const [editorValueName, setEditorValueName] = useState('');
  const [editorValueType, setEditorValueType] = useState<RegistryValueType>('REG_SZ');
  const [error, setError] = useState('');
  const [hive, setHive] = useState<RegistryHive>('HKLM');
  const [isClosingSession, setIsClosingSession] = useState(false);
  const [isLoadingKey, setIsLoadingKey] = useState(false);
  const [isOpeningSession, setIsOpeningSession] = useState(false);
  const [keyPath, setKeyPath] = useState('Software');
  const [pendingAction, setPendingAction] = useState<PendingRegistryAction | null>(null);
  const [selectedValue, setSelectedValue] = useState<RegistryValueEntry | null>(null);
  const [session, setSession] = useState<RegistrySession | null>(null);
  const [statusMessage, setStatusMessage] = useState('');
  const [subkeys, setSubkeys] = useState<string[]>([]);
  const [values, setValues] = useState<RegistryValueEntry[]>([]);
  const activeSession = Boolean(session && !['closed', 'failed'].includes(session.status));
  const windowsBeacon = isWindowsBeacon(beacon);

  const nextRequestId = useCallback(() => {
    requestCounterRef.current += 1;
    return `reg-${requestCounterRef.current}`;
  }, []);

  const sendRegistryMessage = useCallback((payload: Record<string, unknown>) => {
    clientRef.current?.sendMessage(payload);
  }, []);

  const loadKey = useCallback((nextHive: RegistryHive, nextKeyPath: string) => {
    const normalizedPath = nextKeyPath.trim().replace(/\//g, '\\').replace(/^\\+|\\+$/g, '');
    setHive(nextHive);
    setKeyPath(normalizedPath);
    setIsLoadingKey(true);
    setError('');
    setSelectedValue(null);
    sendRegistryMessage({
      hive: nextHive,
      key_path: normalizedPath,
      op: 'reg_list_key',
      request_id: nextRequestId(),
    });
  }, [nextRequestId, sendRegistryMessage]);

  const requestInitialKey = useCallback(() => {
    if (hasRequestedInitialKeyRef.current) {
      return;
    }
    hasRequestedInitialKeyRef.current = true;
    window.setTimeout(() => loadKey(hive, keyPath), 0);
  }, [hive, keyPath, loadKey]);

  const readValue = useCallback((value: RegistryValueEntry) => {
    setSelectedValue(value);
    setEditorValueName(value.name);
    setEditorValueType(value.type === 'REG_DWORD' ? 'REG_DWORD' : 'REG_SZ');
    setEditorValue(value.value === undefined || value.value === null ? '' : String(value.value));
    sendRegistryMessage({
      hive,
      key_path: keyPath,
      op: 'reg_read_value',
      request_id: nextRequestId(),
      value_name: value.name,
    });
  }, [hive, keyPath, nextRequestId, sendRegistryMessage]);

  const handleRegistryMessage = useCallback((message: ShellSessionMessage) => {
    if (message.session?.session_type === 'registry') {
      setSession(message.session);
    }
    if (message.op === 'attached' || message.op === 'opened') {
      setError('');
      requestInitialKey();
      return;
    }
    if (message.op === 'reg_list_key') {
      setIsLoadingKey(false);
      if (message.ok === false) {
        setError(registryErrorMessage(message));
        return;
      }
      setHive((message.hive as RegistryHive) ?? hive);
      setKeyPath(message.key_path ?? '');
      setSubkeys(message.subkeys ?? []);
      setValues(message.values ?? []);
      setStatusMessage(`${message.hive ?? hive}\\${message.key_path ?? ''}`);
      setError('');
      return;
    }
    if (message.op === 'reg_read_value') {
      if (message.ok === false) {
        setError(registryErrorMessage(message));
        return;
      }
      const value = {
        name: message.value_name ?? '',
        type: message.value_type ?? 'REG_NONE',
        value: message.value,
        writable: Boolean(message.writable ?? ['REG_DWORD', 'REG_SZ'].includes(message.value_type ?? '')),
      };
      setSelectedValue(value);
      setEditorValueName(value.name);
      setEditorValueType(value.type === 'REG_DWORD' ? 'REG_DWORD' : 'REG_SZ');
      setEditorValue(value.value === undefined || value.value === null ? '' : String(value.value));
      setError('');
      return;
    }
    if (message.op === 'reg_confirm_token') {
      const action = pendingActionRef.current;
      if (!action || action.requestId !== message.request_id || !message.value_name) {
        return;
      }
      sendRegistryMessage({
        confirm_token: message.confirm_token,
        hive: action.hive,
        key_path: action.keyPath,
        op: action.action,
        request_id: nextRequestId(),
        value: action.value,
        value_name: action.valueName,
        value_type: action.valueType,
      });
      pendingActionRef.current = null;
      setPendingAction(null);
      setStatusMessage(action.action === 'reg_write_value' ? 'Applying registry value.' : 'Deleting registry value.');
      return;
    }
    if (message.op === 'reg_write_value' || message.op === 'reg_delete_value') {
      if (message.ok === false) {
        setError(registryErrorMessage(message));
        return;
      }
      setStatusMessage(message.op === 'reg_write_value' ? 'Registry value saved.' : 'Registry value deleted.');
      loadKey(hive, keyPath);
      return;
    }
    if (message.op === 'closed') {
      clientRef.current?.stop();
      return;
    }
    if (message.op === 'error') {
      setError(registryErrorMessage(message));
    }
  }, [hive, keyPath, loadKey, nextRequestId, requestInitialKey, sendRegistryMessage]);

  const handleSessionStatus = useCallback((status: ShellSessionConnectionStatus, message?: string) => {
    setConnectionStatus(status);
    if (message) {
      setError(message);
    } else if (status === 'connected') {
      setError('');
    }
  }, []);

  useEffect(() => () => clientRef.current?.stop(), []);

  useEffect(() => {
    if (activeSession && connectionStatus === 'connected') {
      requestInitialKey();
    }
  }, [activeSession, connectionStatus, requestInitialKey]);

  async function handleOpenSession(): Promise<void> {
    setIsOpeningSession(true);
    setError('');
    setValues([]);
    setSubkeys([]);
    setSelectedValue(null);
    hasRequestedInitialKeyRef.current = false;
    try {
      const created = await createRegistrySession(connection.baseUrl, connection.accessToken, {
        beacon_id: beacon.id,
      });
      setSession(created);
      clientRef.current?.stop();
      const client = new ShellSessionClient({
        accessToken: connection.accessToken,
        baseUrl: connection.baseUrl,
        onMessage: handleRegistryMessage,
        onStatusChange: handleSessionStatus,
        sessionId: created.id,
      });
      clientRef.current = client;
      client.start();
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Unable to open registry session.';
      setError(message);
    } finally {
      setIsOpeningSession(false);
    }
  }

  async function handleCloseSession(): Promise<void> {
    if (!session) {
      return;
    }
    setIsClosingSession(true);
    setError('');
    try {
      if (clientRef.current?.isOpen()) {
        clientRef.current.closeSession();
      } else {
        const closed = await closeRegistrySession(connection.baseUrl, connection.accessToken, session.id);
        setSession(closed);
      }
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Unable to close registry session.';
      setError(message);
    } finally {
      setIsClosingSession(false);
    }
  }

  function prepareWrite(): void {
    const name = editorValueName.trim();
    if (!name) {
      setError('Value name is required.');
      return;
    }
    let value: number | string = editorValue;
    if (editorValueType === 'REG_DWORD') {
      const parsedValue = Number(editorValue);
      if (!Number.isInteger(parsedValue) || parsedValue < 0 || parsedValue > 0xffffffff) {
        setError('DWORD value must be an integer from 0 to 4294967295.');
        return;
      }
      value = parsedValue;
    }
    const action = {
      action: 'reg_write_value' as const,
      hive,
      keyPath,
      requestId: nextRequestId(),
      value,
      valueName: name,
      valueType: editorValueType,
    };
    pendingActionRef.current = action;
    setPendingAction(action);
  }

  function prepareDelete(): void {
    const name = selectedValue?.name ?? editorValueName.trim();
    if (!name) {
      setError('Select a registry value to delete.');
      return;
    }
    const action = {
      action: 'reg_delete_value' as const,
      hive,
      keyPath,
      requestId: nextRequestId(),
      valueName: name,
    };
    pendingActionRef.current = action;
    setPendingAction(action);
  }

  function confirmPendingAction(): void {
    if (!pendingAction) {
      return;
    }
    sendRegistryMessage({
      hive: pendingAction.hive,
      key_path: pendingAction.keyPath,
      op: pendingAction.action === 'reg_write_value' ? 'reg_prepare_write_value' : 'reg_prepare_delete_value',
      request_id: pendingAction.requestId,
      value: pendingAction.value,
      value_name: pendingAction.valueName,
      value_type: pendingAction.valueType,
    });
  }

  if (!windowsBeacon) {
    return (
      <div className="registry-panel">
        <div className="beacon-operation-locked">
          <Database aria-hidden="true" size={17} strokeWidth={2} />
          <div>
            <strong>Registry unavailable.</strong>
            <span>Windows registry sessions require a Windows beacon.</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="registry-panel">
      <div className="shell-session-toolbar">
        <button
          className="primary-button shell-session-action"
          disabled={activeSession || isOpeningSession || !beacon.transport_connected}
          onClick={() => void handleOpenSession()}
          type="button"
        >
          <Database aria-hidden="true" size={15} strokeWidth={2.2} />
          <span>{isOpeningSession ? 'Opening' : 'Open'}</span>
        </button>
        <button
          className="secondary-button shell-session-action"
          disabled={!activeSession || isClosingSession}
          onClick={() => void handleCloseSession()}
          type="button"
        >
          <X aria-hidden="true" size={15} strokeWidth={2.2} />
          <span>{isClosingSession ? 'Closing' : 'Close'}</span>
        </button>
        <button
          aria-label="Refresh registry key"
          className="secondary-button shell-session-action"
          disabled={!activeSession || isLoadingKey}
          onClick={() => loadKey(hive, keyPath)}
          type="button"
        >
          <RefreshCw aria-hidden="true" size={15} strokeWidth={2.2} />
          <span>{isLoadingKey ? 'Loading' : 'Refresh'}</span>
        </button>
      </div>

      <div className="shell-session-status-strip">
        <span data-testid="registry-session-status">{session?.status ?? connectionStatus}</span>
        <span>{connectionStatus}</span>
        <span>{beacon.transport_connected ? 'Transport online' : 'Transport offline'}</span>
      </div>

      {error ? <p className="task-queue-error" role="alert">{error}</p> : null}

      <div className="registry-target-bar">
        <div className="registry-hive-tabs" role="tablist" aria-label="Registry hives">
          {registryHives.map((item) => (
            <button
              aria-selected={item === hive}
              className={item === hive ? 'is-selected' : ''}
              disabled={!activeSession}
              key={item}
              onClick={() => loadKey(item, item === 'HKLM' ? 'Software' : '')}
              role="tab"
              type="button"
            >
              {item}
            </button>
          ))}
        </div>
        <label>
          <span>Key</span>
          <input
            aria-label="Registry key path"
            disabled={!activeSession}
            onChange={(event) => setKeyPath(event.target.value)}
            value={keyPath}
          />
        </label>
        <button className="secondary-button" disabled={!activeSession} onClick={() => loadKey(hive, keyPath)} type="button">
          <FolderKey aria-hidden="true" size={15} strokeWidth={2.1} />
          <span>Browse</span>
        </button>
      </div>

      <div className="registry-grid">
        <section className="registry-key-list" aria-label="Registry subkeys">
          <div className="task-result-panel-head">
            <div>
              <strong>Subkeys</strong>
              <span>{statusMessage || `${hive}\\${keyPath}`}</span>
            </div>
          </div>
          {subkeys.length === 0 ? (
            <div className="task-empty-state">{activeSession ? 'No subkeys.' : 'Open a registry session.'}</div>
          ) : (
            <div className="registry-subkey-list">
              {subkeys.map((subkey) => (
                <button key={subkey} onClick={() => loadKey(hive, joinRegistryPath(keyPath, subkey))} type="button">
                  <FolderKey aria-hidden="true" size={15} strokeWidth={2.1} />
                  <span>{subkey}</span>
                </button>
              ))}
            </div>
          )}
        </section>

        <section className="registry-value-list" aria-label="Registry values">
          <table className="file-browser-table">
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Type</th>
                <th scope="col">Value</th>
                <th scope="col">Mode</th>
              </tr>
            </thead>
            <tbody>
              {values.length === 0 ? (
                <tr>
                  <td colSpan={4}>
                    <span className="file-browser-empty">{activeSession ? 'No values.' : 'Open a registry session.'}</span>
                  </td>
                </tr>
              ) : (
                values.map((value) => (
                  <tr key={`${value.name}-${value.type}`}>
                    <td>
                      <button className="file-browser-entry-button" onClick={() => readValue(value)} type="button">
                        <Edit3 aria-hidden="true" size={15} strokeWidth={2.1} />
                        <span>{value.name || '(Default)'}</span>
                      </button>
                    </td>
                    <td>{value.type}</td>
                    <td>
                      <span className="beacon-mono">{registryValueDisplay(value)}</span>
                    </td>
                    <td>{value.writable ? 'Editable' : 'Read-only'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </section>

        <aside className="registry-editor" aria-label="Registry value editor">
          <div className="task-result-panel-head">
            <div>
              <strong>Value editor</strong>
              <span>{selectedValue ? selectedValue.name || '(Default)' : 'New value'}</span>
            </div>
          </div>
          <label>
            <span>Name</span>
            <input
              aria-label="Registry value name"
              disabled={!activeSession}
              onChange={(event) => setEditorValueName(event.target.value)}
              value={editorValueName}
            />
          </label>
          <label>
            <span>Type</span>
            <select
              aria-label="Registry value type"
              disabled={!activeSession}
              onChange={(event) => setEditorValueType(event.target.value as RegistryValueType)}
              value={editorValueType}
            >
              <option value="REG_SZ">REG_SZ</option>
              <option value="REG_DWORD">REG_DWORD</option>
            </select>
          </label>
          <label>
            <span>Value</span>
            <input
              aria-label="Registry value data"
              disabled={!activeSession || (selectedValue ? !selectedValue.writable : false)}
              onChange={(event) => setEditorValue(event.target.value)}
              type={editorValueType === 'REG_DWORD' ? 'number' : 'text'}
              value={editorValue}
            />
          </label>
          <div className="registry-editor-actions">
            <button
              className="primary-button"
              disabled={!activeSession || (selectedValue ? !selectedValue.writable : false)}
              onClick={prepareWrite}
              type="button"
            >
              <Save aria-hidden="true" size={15} strokeWidth={2.2} />
              <span>Save</span>
            </button>
            <button
              className="secondary-button"
              disabled={!activeSession || !selectedValue}
              onClick={prepareDelete}
              type="button"
            >
              <Trash2 aria-hidden="true" size={15} strokeWidth={2.2} />
              <span>Delete</span>
            </button>
          </div>
        </aside>
      </div>

      {pendingAction ? (
        <ModalShell
          ariaLabel="Confirm registry operation"
          onClose={() => {
            pendingActionRef.current = null;
            setPendingAction(null);
          }}
          subtitle={`${pendingAction.hive}\\${pendingAction.keyPath}`}
          title={pendingAction.action === 'reg_write_value' ? 'Save registry value' : 'Delete registry value'}
        >
          <div className="registry-confirm-body">
            <p>
              {pendingAction.action === 'reg_write_value' ? 'Save' : 'Delete'}{' '}
              <strong>{pendingAction.valueName || '(Default)'}</strong>
            </p>
            <div className="registry-editor-actions">
              <button
                className="secondary-button"
                onClick={() => {
                  pendingActionRef.current = null;
                  setPendingAction(null);
                }}
                type="button"
              >
                <X aria-hidden="true" size={15} strokeWidth={2.2} />
                <span>Cancel</span>
              </button>
              <button className="primary-button" onClick={confirmPendingAction} type="button">
                <Save aria-hidden="true" size={15} strokeWidth={2.2} />
                <span>Confirm</span>
              </button>
            </div>
          </div>
        </ModalShell>
      ) : null}
    </div>
  );
}
