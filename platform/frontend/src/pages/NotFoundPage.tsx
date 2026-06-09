import { Link } from 'react-router-dom';
import { SearchX } from 'lucide-react';

export function NotFoundPage() {
  return (
    <main className="not-found-page page-enter">
      <section className="workspace-panel not-found-panel">
        <div className="panel-icon" aria-hidden="true">
          <SearchX size={18} strokeWidth={2} />
        </div>
        <h1>Page not found</h1>
        <p className="muted-text">The requested Xero route is unavailable.</p>
        <Link className="secondary-link" to="/login">
          Return to login
        </Link>
      </section>
    </main>
  );
}
