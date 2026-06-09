import { useState } from 'react';
import { Crosshair, Play, RadioTower, Search } from 'lucide-react';

import { AppShell } from '../components/AppShell';
import { C2RequiredPanel } from '../components/C2RequiredPanel';
import { useC2Connection } from '../useC2Connection';

interface ReconTool {
  description: string;
  name: string;
}

const reconTools: ReconTool[] = [
  { name: 'Subdomain enumeration', description: 'Discover DNS names and passive scope expansion.' },
  { name: 'Port discovery', description: 'Identify exposed TCP services for scoped targets.' },
  { name: 'HTTP probe', description: 'Fingerprint web services and response metadata.' },
];

export function ReconPage() {
  const { connection } = useC2Connection();
  const [runs, setRuns] = useState<string[]>([]);

  function queueRun(toolName: string) {
    setRuns((currentRuns) => [`${toolName} queued`, ...currentRuns]);
  }

  return (
    <AppShell description="Discovery tool orchestration" section="recon" title="Recon">
      {!connection ? (
        <C2RequiredPanel />
      ) : (
        <div className="lifecycle-grid">
          <section className="workspace-panel recon-panel" aria-label="Recon tools">
            <div className="panel-header">
              <div>
                <h2>Recon tools</h2>
                <p className="muted-text">Trigger scoped discovery jobs through the connected backend.</p>
              </div>
              <div className="panel-icon" aria-hidden="true">
                <Crosshair size={18} strokeWidth={2} />
              </div>
            </div>

            <div className="tool-list">
              {reconTools.map((tool) => (
                <div className="tool-row" key={tool.name}>
                  <div>
                    <strong>{tool.name}</strong>
                    <span>{tool.description}</span>
                  </div>
                  <button className="secondary-button" type="button" onClick={() => queueRun(tool.name)}>
                    <Play aria-hidden="true" size={14} strokeWidth={2} />
                    <span>Queue</span>
                  </button>
                </div>
              ))}
            </div>
          </section>

          <section className="workspace-panel" aria-label="Recon runs">
            <div className="panel-header">
              <div>
                <h2>Runs</h2>
                <p className="muted-text">Queued discovery activity.</p>
              </div>
              <div className="panel-icon" aria-hidden="true">
                <Search size={18} strokeWidth={2} />
              </div>
            </div>

            <div className="dashboard-list">
              {runs.length === 0 ? (
                <div className="empty-state">
                  <RadioTower aria-hidden="true" size={18} strokeWidth={2} />
                  <div>
                    <strong>No recon runs queued.</strong>
                    <span>Runs will appear after a tool is queued.</span>
                  </div>
                </div>
              ) : (
                runs.map((run, index) => (
                  <div className="dashboard-row" key={`${run}-${index}`}>
                    <span>{run}</span>
                    <strong>Pending</strong>
                  </div>
                ))
              )}
            </div>
          </section>
        </div>
      )}
    </AppShell>
  );
}
