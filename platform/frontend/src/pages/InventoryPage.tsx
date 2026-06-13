import { Database, Layers3, RefreshCw, Search, Server, Wifi } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import type { Asset, AssetGroup, AssetSource, AssetType } from '../api';
import { getAsset, getAssetGroups, getAssets } from '../api';
import { AppShell } from '../components/AppShell';
import { C2RequiredPanel } from '../components/C2RequiredPanel';
import { useC2Connection } from '../useC2Connection';

const PAGE_SIZE = 25;

function assetTypeLabel(type: AssetType): string {
  if (type === 'beacon_host') {
    return 'Beacon host';
  }
  if (type === 'discovered_host') {
    return 'Discovered host';
  }
  return 'Service';
}

function sourceLabel(source: AssetSource | string): string {
  return source === 'beacon' ? 'Beacon' : 'Scan';
}

function formatTimestamp(value: string | null | undefined): string {
  if (!value) {
    return '-';
  }
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) {
    return '-';
  }
  return new Intl.DateTimeFormat(undefined, {
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    month: 'short',
  }).format(new Date(parsed));
}

function assetIcon(type: AssetType) {
  if (type === 'service') {
    return <Wifi aria-hidden="true" size={15} strokeWidth={2.1} />;
  }
  if (type === 'beacon_host') {
    return <Server aria-hidden="true" size={15} strokeWidth={2.1} />;
  }
  return <Database aria-hidden="true" size={15} strokeWidth={2.1} />;
}

function metadataValue(value: unknown): string {
  if (value === null || typeof value === 'undefined') {
    return '-';
  }
  if (Array.isArray(value)) {
    return value.join(', ');
  }
  if (typeof value === 'object') {
    return JSON.stringify(value);
  }
  return String(value);
}

function groupCriterionLabel(group: AssetGroup): string {
  if (group.criterion_type === 'subnet') {
    return group.criterion_value ?? 'Subnet';
  }
  if (group.criterion_type === 'domain') {
    return group.criterion_value ?? 'Domain';
  }
  if (group.criterion_type === 'workgroup') {
    return group.criterion_value ? group.criterion_value.toUpperCase() : 'Workgroup';
  }
  if (group.criterion_type === 'os') {
    return group.criterion_value ?? 'OS';
  }
  return group.criterion_value ?? group.group_key;
}

function AssetDetail({ asset, error, isLoading }: { asset: Asset | null; error: string; isLoading: boolean }) {
  if (isLoading) {
    return (
      <aside className="workspace-panel asset-detail-panel" aria-label="Asset detail">
        <div className="empty-state">
          <RefreshCw aria-hidden="true" size={18} strokeWidth={2} />
          <div>
            <strong>Loading asset.</strong>
            <span>Detail data is coming from C2.</span>
          </div>
        </div>
      </aside>
    );
  }

  if (error) {
    return (
      <aside className="workspace-panel asset-detail-panel" aria-label="Asset detail">
        <p className="task-queue-error" role="alert">{error}</p>
      </aside>
    );
  }

  if (!asset) {
    return (
      <aside className="workspace-panel asset-detail-panel" aria-label="Asset detail">
        <div className="empty-state">
          <Database aria-hidden="true" size={18} strokeWidth={2} />
          <div>
            <strong>No asset selected.</strong>
            <span>Select an asset row to inspect it.</span>
          </div>
        </div>
      </aside>
    );
  }

  const identifiers = asset.identifiers ?? [];
  const linkedBeacons = asset.linked_beacons ?? [];
  const relationships = asset.relationships ?? [];
  const observations = asset.observations ?? [];
  const groups = asset.groups ?? [];

  return (
    <aside className="workspace-panel asset-detail-panel" aria-label="Asset detail">
      <div className="panel-header">
        <div>
          <h2>{asset.display_name}</h2>
          <p className="muted-text">{asset.primary_ip ?? asset.hostname ?? asset.id}</p>
        </div>
        <span className={`asset-type-chip asset-type-${asset.asset_type}`}>
          {assetIcon(asset.asset_type)}
          {assetTypeLabel(asset.asset_type)}
        </span>
      </div>

      <dl className="asset-detail-grid">
        <div>
          <dt>Source</dt>
          <dd>{sourceLabel(asset.source)}</dd>
        </div>
        <div>
          <dt>Last seen</dt>
          <dd>{formatTimestamp(asset.last_seen)}</dd>
        </div>
        <div>
          <dt>Hostname</dt>
          <dd>{asset.hostname ?? '-'}</dd>
        </div>
        <div>
          <dt>Domain</dt>
          <dd>{asset.domain ?? '-'}</dd>
        </div>
        <div>
          <dt>OS</dt>
          <dd>{asset.os ?? '-'}</dd>
        </div>
        <div>
          <dt>Role</dt>
          <dd>{asset.role ?? '-'}</dd>
        </div>
      </dl>

      <section className="asset-detail-section" aria-label="Asset groups">
        <h3>Auto Groups</h3>
        {groups.length === 0 ? (
          <p className="muted-text">No groups assigned.</p>
        ) : (
          <div className="asset-detail-list">
            {groups.map((group) => (
              <div className="asset-detail-row" key={group.id}>
                <span>{group.criterion_type ?? group.source}</span>
                <strong>{group.name}</strong>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="asset-detail-section" aria-label="Identifiers">
        <h3>Identifiers</h3>
        {identifiers.length === 0 ? (
          <p className="muted-text">No identifiers recorded.</p>
        ) : (
          <div className="asset-detail-list">
            {identifiers.map((identifier) => (
              <div className="asset-detail-row" key={identifier.id}>
                <span>{identifier.kind}</span>
                <strong>{identifier.value}</strong>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="asset-detail-section" aria-label="Linked beacons">
        <h3>Linked Beacons</h3>
        {linkedBeacons.length === 0 ? (
          <p className="muted-text">No linked beacon.</p>
        ) : (
          <div className="asset-detail-list">
            {linkedBeacons.map((link) => (
              <div className="asset-detail-row" key={link.id}>
                <span>{link.hostname ?? link.status ?? 'beacon'}</span>
                <strong>{link.beacon_id}</strong>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="asset-detail-section" aria-label="Relationships">
        <h3>Relationships</h3>
        {relationships.length === 0 ? (
          <p className="muted-text">No relationships recorded.</p>
        ) : (
          <div className="asset-detail-list">
            {relationships.map((relationship) => (
              <div className="asset-detail-row" key={relationship.id}>
                <span>{relationship.relationship_type}</span>
                <strong>{relationship.related_asset_name ?? relationship.related_asset_id}</strong>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="asset-detail-section" aria-label="Recent observations">
        <h3>Recent Observations</h3>
        {observations.length === 0 ? (
          <p className="muted-text">No observations recorded.</p>
        ) : (
          <div className="asset-observation-list">
            {observations.slice(0, 6).map((observation) => (
              <div className="asset-observation" key={observation.id}>
                <span>{formatTimestamp(observation.observed_at)}</span>
                <strong>{observation.observation_type}</strong>
              </div>
            ))}
          </div>
        )}
      </section>

      {Object.keys(asset.metadata).length > 0 ? (
        <section className="asset-detail-section" aria-label="Metadata">
          <h3>Metadata</h3>
          <div className="asset-detail-list">
            {Object.entries(asset.metadata).map(([key, value]) => (
              <div className="asset-detail-row" key={key}>
                <span>{key}</span>
                <strong>{metadataValue(value)}</strong>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </aside>
  );
}

export function InventoryPage() {
  const { connection } = useC2Connection();
  const [assets, setAssets] = useState<Asset[]>([]);
  const [groups, setGroups] = useState<AssetGroup[]>([]);
  const [assetType, setAssetType] = useState<AssetType | 'all'>('all');
  const [detailAsset, setDetailAsset] = useState<Asset | null>(null);
  const [detailError, setDetailError] = useState('');
  const [groupError, setGroupError] = useState('');
  const [isGroupsLoading, setIsGroupsLoading] = useState(false);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [listError, setListError] = useState('');
  const [page, setPage] = useState(0);
  const [query, setQuery] = useState('');
  const [refreshTick, setRefreshTick] = useState(0);
  const [selectedAssetId, setSelectedAssetId] = useState('');
  const [selectedGroupId, setSelectedGroupId] = useState('');
  const [source, setSource] = useState<AssetSource | 'all'>('all');
  const [total, setTotal] = useState(0);
  const trimmedQuery = query.trim();

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const currentOffset = page * PAGE_SIZE;
  const selectedGroup = useMemo(
    () => groups.find((group) => group.id === selectedGroupId) ?? null,
    [groups, selectedGroupId],
  );
  const selectedAsset = useMemo(
    () => assets.find((asset) => asset.id === selectedAssetId) ?? assets[0] ?? null,
    [assets, selectedAssetId],
  );

  useEffect(() => {
    if (!connection) {
      queueMicrotask(() => {
        setGroups([]);
        setSelectedGroupId('');
      });
      return;
    }

    let ignore = false;
    queueMicrotask(() => {
      if (!ignore) {
        setIsGroupsLoading(true);
        setGroupError('');
      }
    });
    getAssetGroups(connection.baseUrl, connection.accessToken, { limit: 100, type: 'auto' })
      .then((payload) => {
        if (ignore) {
          return;
        }
        setGroups(payload.items);
        if (selectedGroupId && !payload.items.some((group) => group.id === selectedGroupId)) {
          setSelectedGroupId('');
        }
      })
      .catch((error: unknown) => {
        if (!ignore) {
          setGroups([]);
          setSelectedGroupId('');
          setGroupError(error instanceof Error ? error.message : 'Asset groups failed to load.');
        }
      })
      .finally(() => {
        if (!ignore) {
          setIsGroupsLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [connection, refreshTick, selectedGroupId]);

  useEffect(() => {
    if (!connection) {
      return;
    }

    let ignore = false;
    queueMicrotask(() => {
      if (!ignore) {
        setIsLoading(true);
        setListError('');
      }
    });

    getAssets(connection.baseUrl, connection.accessToken, {
      limit: PAGE_SIZE,
      offset: currentOffset,
      q: trimmedQuery || undefined,
      source,
      type: assetType,
      groupId: selectedGroupId || undefined,
    })
      .then((payload) => {
        if (ignore) {
          return;
        }
        setAssets(payload.items);
        setTotal(payload.total);
        if (payload.items.length === 0) {
          setSelectedAssetId('');
        } else if (!payload.items.some((asset) => asset.id === selectedAssetId)) {
          setSelectedAssetId(payload.items[0].id);
        }
      })
      .catch((error: unknown) => {
        if (!ignore) {
          setAssets([]);
          setTotal(0);
          setSelectedAssetId('');
          setListError(error instanceof Error ? error.message : 'Asset inventory failed to load.');
        }
      })
      .finally(() => {
        if (!ignore) {
          setIsLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [assetType, connection, currentOffset, refreshTick, selectedAssetId, selectedGroupId, source, trimmedQuery]);

  useEffect(() => {
    if (!connection || !selectedAssetId) {
      return;
    }

    let ignore = false;
    queueMicrotask(() => {
      if (!ignore) {
        setIsDetailLoading(true);
        setDetailError('');
      }
    });

    getAsset(connection.baseUrl, connection.accessToken, selectedAssetId)
      .then((asset) => {
        if (!ignore) {
          setDetailAsset(asset);
        }
      })
      .catch((error: unknown) => {
        if (!ignore) {
          setDetailAsset(null);
          setDetailError(error instanceof Error ? error.message : 'Asset detail failed to load.');
        }
      })
      .finally(() => {
        if (!ignore) {
          setIsDetailLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [connection, selectedAssetId]);

  function resetPageAndSetType(nextType: AssetType | 'all'): void {
    setPage(0);
    setAssetType(nextType);
  }

  function resetPageAndSetSource(nextSource: AssetSource | 'all'): void {
    setPage(0);
    setSource(nextSource);
  }

  function resetPageAndSetQuery(nextQuery: string): void {
    setPage(0);
    setQuery(nextQuery);
  }

  function selectGroup(groupId: string): void {
    setPage(0);
    setSelectedAssetId('');
    setSelectedGroupId(groupId);
  }

  return (
    <AppShell description="Discovered hosts, services, and C2-linked systems" section="assets" title="Assets" wide>
      {!connection ? (
        <C2RequiredPanel />
      ) : (
        <div className="asset-inventory-workspace">
          <aside className="workspace-panel asset-groups-panel" aria-label="Automatic asset groups">
            <div className="panel-header">
              <div>
                <h2>Auto Groups</h2>
                <p className="muted-text">{groups.length} active groups</p>
              </div>
              <Layers3 aria-hidden="true" size={18} strokeWidth={2.1} />
            </div>
            {groupError ? <p className="task-queue-error" role="alert">{groupError}</p> : null}
            <div className="asset-group-list">
              <button
                className={!selectedGroupId ? 'asset-group-button is-selected' : 'asset-group-button'}
                onClick={() => selectGroup('')}
                type="button"
              >
                <span>
                  <strong>All assets</strong>
                  <em>No group filter</em>
                </span>
                <b>{total}</b>
              </button>
              {isGroupsLoading && groups.length === 0 ? <p className="muted-text">Loading groups.</p> : null}
              {!isGroupsLoading && groups.length === 0 ? <p className="muted-text">No auto groups yet.</p> : null}
              {groups.map((group) => (
                <button
                  className={group.id === selectedGroupId ? 'asset-group-button is-selected' : 'asset-group-button'}
                  key={group.id}
                  onClick={() => selectGroup(group.id)}
                  type="button"
                >
                  <span>
                    <strong>{group.name}</strong>
                    <em>{groupCriterionLabel(group)}</em>
                  </span>
                  <b>{group.member_count}</b>
                </button>
              ))}
            </div>
          </aside>
          <section className="workspace-panel asset-list-panel" aria-label="Asset inventory">
            <div className="panel-header">
              <div>
                <h2>Inventory</h2>
                <p className="muted-text">
                  {total} assets tracked{selectedGroup ? ` in ${selectedGroup.name}` : ''}
                </p>
              </div>
              <button className="secondary-button" disabled={isLoading} onClick={() => setRefreshTick((value) => value + 1)} type="button">
                <RefreshCw aria-hidden="true" size={15} strokeWidth={2.1} />
                <span>{isLoading ? 'Refreshing' : 'Refresh'}</span>
              </button>
            </div>

            <div className="asset-filter-bar">
              <label className="module-search">
                <Search aria-hidden="true" size={14} strokeWidth={2} />
                <input
                  aria-label="Search assets"
                  onChange={(event) => resetPageAndSetQuery(event.target.value)}
                  placeholder="Search assets"
                  value={query}
                />
              </label>
              <select
                aria-label="Filter asset type"
                onChange={(event) => resetPageAndSetType(event.target.value as AssetType | 'all')}
                value={assetType}
              >
                <option value="all">All types</option>
                <option value="beacon_host">Beacon hosts</option>
                <option value="discovered_host">Discovered hosts</option>
                <option value="service">Services</option>
              </select>
              <select
                aria-label="Filter asset source"
                onChange={(event) => resetPageAndSetSource(event.target.value as AssetSource | 'all')}
                value={source}
              >
                <option value="all">All sources</option>
                <option value="beacon">Beacon</option>
                <option value="scan">Scan</option>
              </select>
            </div>

            {listError ? <p className="task-queue-error" role="alert">{listError}</p> : null}
            <div className="asset-table-wrap">
              <table className="asset-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Type</th>
                    <th>IP</th>
                    <th>Hostname</th>
                    <th>Source</th>
                    <th>Last seen</th>
                  </tr>
                </thead>
                <tbody>
                  {isLoading && assets.length === 0 ? (
                    <tr>
                      <td colSpan={6}>Loading assets.</td>
                    </tr>
                  ) : null}
                  {!isLoading && assets.length === 0 ? (
                    <tr>
                      <td colSpan={6}>No assets match current filters.</td>
                    </tr>
                  ) : assets.map((asset) => (
                    <tr
                      className={asset.id === selectedAssetId ? 'is-selected' : ''}
                      key={asset.id}
                      onClick={() => setSelectedAssetId(asset.id)}
                    >
                      <td>
                        <span className="asset-name-cell">
                          {assetIcon(asset.asset_type)}
                          <strong>{asset.display_name}</strong>
                        </span>
                      </td>
                      <td>
                        <span className={`asset-type-chip asset-type-${asset.asset_type}`}>{assetTypeLabel(asset.asset_type)}</span>
                      </td>
                      <td>{asset.primary_ip ?? '-'}</td>
                      <td>{asset.hostname ?? '-'}</td>
                      <td>{sourceLabel(asset.source)}</td>
                      <td>{formatTimestamp(asset.last_seen)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="asset-pagination">
              <span>
                {total === 0 ? '0-0' : `${currentOffset + 1}-${Math.min(currentOffset + assets.length, total)}`} of {total}
              </span>
              <div>
                <button className="secondary-button" disabled={page === 0 || isLoading} onClick={() => setPage((value) => value - 1)} type="button">
                  Previous
                </button>
                <button
                  className="secondary-button"
                  disabled={page + 1 >= totalPages || isLoading}
                  onClick={() => setPage((value) => value + 1)}
                  type="button"
                >
                  Next
                </button>
              </div>
            </div>
          </section>

          <AssetDetail
            asset={selectedAssetId ? detailAsset ?? selectedAsset : null}
            error={selectedAssetId ? detailError : ''}
            isLoading={Boolean(selectedAssetId) && isDetailLoading}
          />
        </div>
      )}
    </AppShell>
  );
}
