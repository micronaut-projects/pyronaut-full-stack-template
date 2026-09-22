import React from 'react';
import { Link } from 'react-router-dom';

export function Field({ id, label, type = 'text', value, onChange, error, ...rest }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        data-testid={`${id}-input`}
        type={type}
        value={value ?? ''}
        onChange={(event) => onChange(event.target.value)}
        aria-invalid={error ? 'true' : undefined}
        {...rest}
      />
      {error ? <p className="field-error">{error}</p> : null}
    </div>
  );
}

export function Alert({ kind = 'info', children }) {
  if (!children) return null;
  return (
    <p className={`alert alert-${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
      {children}
    </p>
  );
}

export function Page({ title, actions, children }) {
  return (
    <section className="page">
      <header className="page-header">
        <h1>{title}</h1>
        {actions}
      </header>
      {children}
    </section>
  );
}

export function AuthCard({ title, children, footer }) {
  return (
    <div className="auth">
      <div className="auth-card">
        <h1>{title}</h1>
        {children}
        {footer ? <div className="auth-footer">{footer}</div> : null}
      </div>
    </div>
  );
}

export function NotFound({ message = 'Page not found' }) {
  return (
    <Page title="Not found">
      <p>{message}</p>
      <Link className="button" to="/">
        Back to the dashboard
      </Link>
    </Page>
  );
}
