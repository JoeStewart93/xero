import { Binary, RadioTower, ShieldAlert } from 'lucide-react';

import type { ProtocolInfo, ProtocolSecurityEvent, TransportStatus } from '../api';
import { compactDateTime, formatBytes, severityClass } from './c2SettingsDisplay';

export function ProtocolStatusPanel({
  protocolError,
  protocolInfo,
}: {
  protocolError: string;
  protocolInfo: ProtocolInfo | null;
}) {
  return (
    <section className="workspace-panel protocol-panel" aria-label="Protocol status">
      <div className="panel-header">
        <div>
          <h2>Protocol status</h2>
          <p className="muted-text">Binary beacon frame contract advertised by the connected C2 backend.</p>
        </div>
        <div className="panel-icon" aria-hidden="true">
          <Binary size={18} strokeWidth={2} />
        </div>
      </div>

      {protocolError ? (
        <p className="alert-message alert-message--inline" role="alert">
          {protocolError}
        </p>
      ) : null}

      <div className="dashboard-list protocol-status-list" data-testid="protocol-status-panel">
        <div className="dashboard-row">
          <span>Current version</span>
          <strong>{protocolInfo ? `v${protocolInfo.current_version}` : '-'}</strong>
        </div>
        <div className="dashboard-row">
          <span>Supported</span>
          <strong>{protocolInfo ? protocolInfo.supported_versions.map((version) => `v${version}`).join(', ') : '-'}</strong>
        </div>
        <div className="dashboard-row">
          <span>Key exchange</span>
          <strong>{protocolInfo?.key_exchange ?? '-'}</strong>
        </div>
        <div className="dashboard-row">
          <span>Encryption</span>
          <strong>{protocolInfo ? `${protocolInfo.encryption} / ${protocolInfo.integrity}` : '-'}</strong>
        </div>
        <div className="dashboard-row">
          <span>Frame header</span>
          <strong>{protocolInfo ? `${protocolInfo.frame_header_length} bytes` : '-'}</strong>
        </div>
        <div className="dashboard-row">
          <span>Harness</span>
          <strong>{protocolInfo?.frame_harness_enabled ? 'Enabled' : 'Disabled'}</strong>
        </div>
      </div>
    </section>
  );
}

export function TransportStatusPanel({
  transportError,
  transportStatus,
}: {
  transportError: string;
  transportStatus: TransportStatus | null;
}) {
  return (
    <section className="workspace-panel protocol-panel" aria-label="Transport status">
      <div className="panel-header">
        <div>
          <h2>Transport status</h2>
          <p className="muted-text">Live beacon WebSocket limits and connection pressure.</p>
        </div>
        <div className="panel-icon" aria-hidden="true">
          <RadioTower size={18} strokeWidth={2} />
        </div>
      </div>

      {transportError ? (
        <p className="alert-message alert-message--inline" role="alert">
          {transportError}
        </p>
      ) : null}

      <div className="dashboard-list protocol-status-list" data-testid="transport-status-panel">
        <div className="dashboard-row">
          <span>Active WebSockets</span>
          <strong data-testid="transport-active-websockets">
            {transportStatus ? transportStatus.active_websocket_connections : '-'}
          </strong>
        </div>
        <div className="dashboard-row">
          <span>Active long-polls</span>
          <strong data-testid="transport-active-longpolls">{transportStatus ? transportStatus.active_longpoll_requests : '-'}</strong>
        </div>
        <div className="dashboard-row">
          <span>Latest modes</span>
          <strong>
            {transportStatus
              ? `WS ${transportStatus.transport_mode_counts.websocket} / LP ${transportStatus.transport_mode_counts['long-poll']} / REST ${transportStatus.transport_mode_counts.rest}`
              : '-'}
          </strong>
        </div>
        <div className="dashboard-row">
          <span>Send queue</span>
          <strong>{transportStatus ? transportStatus.websocket_send_queue_size : '-'}</strong>
        </div>
        <div className="dashboard-row">
          <span>WS max message</span>
          <strong>{transportStatus ? formatBytes(transportStatus.websocket_max_message_bytes) : '-'}</strong>
        </div>
        <div className="dashboard-row">
          <span>Long-poll max frame</span>
          <strong>{transportStatus ? formatBytes(transportStatus.longpoll_max_frame_bytes) : '-'}</strong>
        </div>
        <div className="dashboard-row">
          <span>Register timeout</span>
          <strong>{transportStatus ? `${transportStatus.websocket_registration_timeout_seconds}s` : '-'}</strong>
        </div>
        <div className="dashboard-row">
          <span>Heartbeat timeout</span>
          <strong>{transportStatus ? `${transportStatus.websocket_heartbeat_timeout_seconds}s` : '-'}</strong>
        </div>
        <div className="dashboard-row">
          <span>Long-poll timeout</span>
          <strong>{transportStatus ? `${transportStatus.longpoll_timeout_seconds}s` : '-'}</strong>
        </div>
        <div className="dashboard-row">
          <span>Native ping</span>
          <strong>
            {transportStatus
              ? `${transportStatus.websocket_ping_interval_seconds}s / ${transportStatus.websocket_ping_timeout_seconds}s`
              : '-'}
          </strong>
        </div>
      </div>
    </section>
  );
}

export function ProtocolSecurityEventsPanel({ protocolEvents }: { protocolEvents: ProtocolSecurityEvent[] }) {
  return (
    <section className="workspace-panel protocol-panel" aria-label="Protocol security events">
      <div className="panel-header">
        <div>
          <h2>Security events</h2>
          <p className="muted-text">Recent binary-frame validation failures recorded by C2.</p>
        </div>
        <div className="panel-icon" aria-hidden="true">
          <ShieldAlert size={18} strokeWidth={2} />
        </div>
      </div>

      {protocolEvents.length === 0 ? (
        <div className="worker-empty-state" data-testid="protocol-security-empty">
          <ShieldAlert aria-hidden="true" size={18} strokeWidth={2} />
          <span>No protocol security events recorded.</span>
        </div>
      ) : (
        <div className="protocol-event-list" data-testid="protocol-security-events">
          {protocolEvents.map((event) => (
            <article className="protocol-event-row" key={event.id}>
              <div>
                <strong>{event.event_type}</strong>
                <span>{event.message}</span>
              </div>
              <div>
                <span className={severityClass(event.severity)}>{event.severity}</span>
                <small>{compactDateTime(event.occurred_at)}</small>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
