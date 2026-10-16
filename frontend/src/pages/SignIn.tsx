// src/pages/SignIn.tsx
import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Activity, AlertCircle } from 'lucide-react';

export default function SignIn() {
  const { login } = useAuth();
  const navigate  = useNavigate();
  const [loading, setLoading]   = useState(false);
  const [error,   setError]     = useState('');
  const [locked,  setLocked]    = useState(false);
  const attempts = useRef(0);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (locked) return;
    const fd = new FormData(e.currentTarget);
    const username = (fd.get('username') as string).trim();
    const password = (fd.get('password') as string);

    setLoading(true);
    setError('');
    try {
      await login(username, password);
      attempts.current = 0;
      navigate('/', { replace: true });
    } catch (err) {
      attempts.current += 1;
      if (attempts.current >= 5) {
        setLocked(true);
        setError('Too many failed attempts. Locked for 30 seconds.');
        setTimeout(() => { setLocked(false); attempts.current = 0; }, 30_000);
      } else {
        setError(`Invalid credentials (${attempts.current}/5 attempts).`);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4"
      style={{ background: 'var(--page)' }}>
      <div className="w-full max-w-sm">

        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl mb-4"
            style={{ background: 'var(--cloud)' }}>
            <Activity size={28} color="white" />
          </div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--text)' }}>
            Telemedicine Operations Portal
          </h1>
          <p className="text-sm mt-1" style={{ color: 'var(--muted)' }}>
            BCSE355L Cloud Architecture Design · VIT University
          </p>
        </div>

        {/* Card */}
        <div className="rounded-2xl p-8 shadow-lg border"
          style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
          <h2 className="text-lg font-semibold mb-6" style={{ color: 'var(--text)' }}>
            Sign in to continue
          </h2>

          {error && (
            <div className="flex items-start gap-2 text-sm rounded-lg px-3 py-2.5 mb-4"
              style={{ background: 'rgba(220,38,38,0.08)', color: 'var(--emergency)', border: '1px solid rgba(220,38,38,0.2)' }}>
              <AlertCircle size={15} className="shrink-0 mt-0.5" />
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate className="space-y-4">
            <div>
              <label htmlFor="username" className="block text-sm font-medium mb-1.5"
                style={{ color: 'var(--text)' }}>
                Username
              </label>
              <input
                id="username" name="username" type="text"
                autoComplete="username" required disabled={locked}
                className="w-full rounded-lg border px-3 py-2.5 text-sm outline-none transition-colors"
                style={{
                  background: 'var(--page)', color: 'var(--text)',
                  borderColor: 'var(--border)',
                }}
                onFocus={e => (e.target.style.borderColor = 'var(--cloud)')}
                onBlur={e  => (e.target.style.borderColor = 'var(--border)')}
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium mb-1.5"
                style={{ color: 'var(--text)' }}>
                Password
              </label>
              <input
                id="password" name="password" type="password"
                autoComplete="current-password" required disabled={locked}
                className="w-full rounded-lg border px-3 py-2.5 text-sm outline-none transition-colors"
                style={{
                  background: 'var(--page)', color: 'var(--text)',
                  borderColor: 'var(--border)',
                }}
                onFocus={e => (e.target.style.borderColor = 'var(--cloud)')}
                onBlur={e  => (e.target.style.borderColor = 'var(--border)')}
              />
            </div>

            <button
              type="submit" disabled={loading || locked}
              className="w-full rounded-lg py-2.5 text-sm font-semibold text-white transition-opacity disabled:opacity-60"
              style={{ background: 'var(--cloud)' }}
            >
              {loading ? 'Signing in…' : locked ? 'Locked' : 'Sign in'}
            </button>
          </form>

          <p className="text-xs mt-5 text-center" style={{ color: 'var(--muted)' }}>
            Demo: <strong>admin</strong> / <strong>hospital123</strong>
          </p>
        </div>
      </div>
    </div>
  );
}
