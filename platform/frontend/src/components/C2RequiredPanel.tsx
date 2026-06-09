import { Cable } from 'lucide-react';
import { Link } from 'react-router-dom';

export function C2RequiredPanel() {
  return (
    <section className="workspace-panel c2-required-panel" aria-label="C2 backend required">
      <div className="panel-header">
        <div>
          <h2>Xero C2 backend required</h2>
          <p className="muted-text">Authenticate to a C2 Core before using discovery workflow controls.</p>
        </div>
        <div className="panel-icon" aria-hidden="true">
          <Cable size={18} strokeWidth={2} />
        </div>
      </div>
      <Link className="secondary-button" to="/settings">
        Open Settings
      </Link>
    </section>
  );
}
