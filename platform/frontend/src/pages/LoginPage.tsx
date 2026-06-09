import { FormEvent, useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';

import { useAuth } from '../useAuth';

export function LoginPage() {
  const { login, session } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setIsSubmitting(true);
    const form = new FormData(event.currentTarget);
    const username = String(form.get('username') ?? '').trim();
    const password = String(form.get('password') ?? '');

    try {
      await login(username, password);
      navigate('/home', { replace: true });
    } catch {
      setError('Invalid username or password.');
    } finally {
      setIsSubmitting(false);
    }
  }

  if (session) {
    return <Navigate to="/home" replace />;
  }

  return (
    <main className="login-page page-enter">
      <section className="login-panel" aria-label="Xero operator login">
        <div className="login-brand-art" aria-hidden="true">
          <img src="/assets/xero-wordmark-banner.png" alt="" />
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          <label>
            Username
            <input name="username" autoComplete="username" />
          </label>
          <label>
            Password
            <input name="password" type="password" autoComplete="current-password" />
          </label>
          <button type="submit" disabled={isSubmitting}>
            <span>{isSubmitting ? 'Signing in...' : 'Log in'}</span>
            {!isSubmitting && <ArrowRight aria-hidden="true" size={15} strokeWidth={2.2} />}
          </button>
        </form>

        {error && (
          <p className="alert-message" role="alert">
            {error}
          </p>
        )}
      </section>
    </main>
  );
}
