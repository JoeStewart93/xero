import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import { Layers3, RefreshCw, RotateCw, SlidersHorizontal } from 'lucide-react';

import type { GroupingRule, GroupingRuleKey } from '../api';
import { getGroupingRules, rerunGrouping, updateGroupingRules } from '../api';
import { AppShell } from '../components/AppShell';
import { C2RequiredPanel } from '../components/C2RequiredPanel';
import { useC2Connection } from '../useC2Connection';

function ruleLabel(ruleKey: GroupingRuleKey): string {
  if (ruleKey === 'subnet') {
    return 'Subnet grouping';
  }
  if (ruleKey === 'domain') {
    return 'Domain and workgroup grouping';
  }
  return 'OS grouping';
}

function ruleDescription(ruleKey: GroupingRuleKey): string {
  if (ruleKey === 'subnet') {
    return 'Assign host assets to deterministic network groups by CIDR prefix.';
  }
  if (ruleKey === 'domain') {
    return 'Group domain-joined hosts and explicitly reported workgroup hosts separately.';
  }
  return 'Group host assets by normalized OS family and major version.';
}

function subnetPrefix(rule: GroupingRule | undefined): number {
  const value = rule?.config.prefix_length;
  return typeof value === 'number' ? value : 24;
}

export function GroupingRulesPage() {
  const { connection } = useC2Connection();
  const [error, setError] = useState('');
  const [isLoading, setLoading] = useState(false);
  const [isRerunning, setRerunning] = useState(false);
  const [message, setMessage] = useState('');
  const [prefixLength, setPrefixLength] = useState(24);
  const [rules, setRules] = useState<GroupingRule[]>([]);
  const [savingKey, setSavingKey] = useState<GroupingRuleKey | ''>('');

  const rulesByKey = useMemo(
    () => new Map(rules.map((rule) => [rule.rule_key, rule])),
    [rules],
  );

  const loadRules = useCallback(async () => {
    if (!connection) {
      setRules([]);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const response = await getGroupingRules(connection.baseUrl, connection.accessToken);
      setRules(response.items);
      setPrefixLength(subnetPrefix(response.items.find((rule) => rule.rule_key === 'subnet')));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Grouping rules failed to load.');
    } finally {
      setLoading(false);
    }
  }, [connection]);

  useEffect(() => {
    const refreshTimer = window.setTimeout(() => {
      void loadRules();
    }, 0);
    return () => window.clearTimeout(refreshTimer);
  }, [loadRules]);

  async function toggleRule(rule: GroupingRule): Promise<void> {
    if (!connection) {
      return;
    }
    setSavingKey(rule.rule_key);
    setError('');
    setMessage('');
    try {
      const response = await updateGroupingRules(
        connection.baseUrl,
        connection.accessToken,
        [{ config: rule.config, enabled: !rule.enabled, rule_key: rule.rule_key }],
        { rerun: true },
      );
      setRules(response.items);
      setMessage(`${ruleLabel(rule.rule_key)} ${rule.enabled ? 'disabled' : 'enabled'} and grouping rerun completed.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Rule update failed.');
    } finally {
      setSavingKey('');
    }
  }

  async function updateSubnetPrefix(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!connection) {
      return;
    }
    setSavingKey('subnet');
    setError('');
    setMessage('');
    try {
      const response = await updateGroupingRules(
        connection.baseUrl,
        connection.accessToken,
        [{ config: { prefix_length: prefixLength }, rule_key: 'subnet' }],
        { rerun: true },
      );
      setRules(response.items);
      setMessage(`Subnet grouping rerun with /${prefixLength}.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Subnet rule update failed.');
    } finally {
      setSavingKey('');
    }
  }

  async function handleRerun(): Promise<void> {
    if (!connection) {
      return;
    }
    setRerunning(true);
    setError('');
    setMessage('');
    try {
      const summary = await rerunGrouping(connection.baseUrl, connection.accessToken);
      setMessage(
        `Rerun processed ${summary.assets_processed} assets, added ${summary.added}, removed ${summary.removed}.`,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Grouping rerun failed.');
    } finally {
      setRerunning(false);
    }
  }

  return (
    <AppShell description="Automatic asset grouping rules" section="settings" title="Settings" wide>
      {!connection ? (
        <C2RequiredPanel />
      ) : (
        <div className="grouping-rules-layout">
          <section className="workspace-panel grouping-rules-overview" aria-label="Grouping rules overview">
            <div className="panel-header">
              <div>
                <h2>Asset grouping</h2>
                <p className="muted-text">Rules run on asset ingestion and can be rerun across the current inventory.</p>
              </div>
              <div className="button-row">
                <button className="secondary-button" disabled={isLoading} onClick={() => void loadRules()} type="button">
                  <RefreshCw aria-hidden="true" size={15} strokeWidth={2.1} />
                  <span>{isLoading ? 'Refreshing' : 'Refresh'}</span>
                </button>
                <button className="primary-button" disabled={isRerunning} onClick={() => void handleRerun()} type="button">
                  <RotateCw aria-hidden="true" size={15} strokeWidth={2.1} />
                  <span>{isRerunning ? 'Running' : 'Rerun'}</span>
                </button>
              </div>
            </div>
            {error ? <p className="task-queue-error" role="alert">{error}</p> : null}
            {message ? <p className="alert-message alert-message--inline">{message}</p> : null}
          </section>

          <section className="workspace-panel grouping-rules-panel" aria-label="Automatic grouping rules">
            <div className="panel-header">
              <div>
                <h2>Rules</h2>
                <p className="muted-text">{rules.length} default rules configured</p>
              </div>
              <SlidersHorizontal aria-hidden="true" size={18} strokeWidth={2.1} />
            </div>
            <div className="grouping-rule-list">
              {rules.map((rule) => (
                <div className="grouping-rule-row" key={rule.rule_key}>
                  <div className="grouping-rule-main">
                    <Layers3 aria-hidden="true" size={16} strokeWidth={2.1} />
                    <span>
                      <strong>{ruleLabel(rule.rule_key)}</strong>
                      <em>{ruleDescription(rule.rule_key)}</em>
                    </span>
                  </div>
                  <span className={rule.enabled ? 'status-chip status-chip--online' : 'status-chip status-chip--offline'}>
                    {rule.enabled ? 'Enabled' : 'Disabled'}
                  </span>
                  <button
                    className="secondary-button"
                    disabled={savingKey === rule.rule_key}
                    onClick={() => void toggleRule(rule)}
                    type="button"
                  >
                    {rule.enabled ? 'Disable' : 'Enable'}
                  </button>
                </div>
              ))}
            </div>
          </section>

          <section className="workspace-panel grouping-rules-panel" aria-label="Subnet rule configuration">
            <div className="panel-header">
              <div>
                <h2>Subnet rule</h2>
                <p className="muted-text">Changing the prefix reruns memberships immediately.</p>
              </div>
              <span className="asset-type-chip">/{prefixLength}</span>
            </div>
            <form className="grouping-prefix-form" onSubmit={updateSubnetPrefix}>
              <label>
                Prefix length
                <input
                  max={32}
                  min={0}
                  onChange={(event) => setPrefixLength(Number(event.target.value))}
                  type="number"
                  value={prefixLength}
                />
              </label>
              <button className="primary-button" disabled={savingKey === 'subnet'} type="submit">
                {savingKey === 'subnet' ? 'Saving' : 'Apply Prefix'}
              </button>
            </form>
            <div className="dashboard-list">
              <div className="dashboard-row">
                <span>Current subnet version</span>
                <strong>{rulesByKey.get('subnet')?.version ?? '-'}</strong>
              </div>
              <div className="dashboard-row">
                <span>Existing disabled-rule memberships</span>
                <strong>Retained unless purge is requested</strong>
              </div>
            </div>
          </section>
        </div>
      )}
    </AppShell>
  );
}
