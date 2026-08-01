'use client';

import { useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense } from 'react';

function LoginForm() {
  const router = useRouter();
  const next = useSearchParams().get('next') || '/';
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError('');
    const res = await fetch('/api/login', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ password }),
    });
    setBusy(false);
    if (res.ok) {
      router.push(next);
      router.refresh();
    } else {
      const { error } = await res.json().catch(() => ({ error: 'login failed' }));
      setError(error ?? 'login failed');
    }
  }

  return (
    <form className="login" onSubmit={submit}>
      <h1>Diasporic Memory</h1>
      <p>Source annotation · post-war visits to Germany</p>
      <input
        type="password"
        value={password}
        autoFocus
        autoComplete="current-password"
        placeholder="Password"
        onChange={(e) => setPassword(e.target.value)}
      />
      <button className="primary" type="submit" disabled={busy || !password}>
        {busy ? 'Checking…' : 'Enter'}
      </button>
      {error && <div className="err">{error}</div>}
    </form>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
