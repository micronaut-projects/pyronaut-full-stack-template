// The page tree.
//
// Every screen is rendered twice: once on the server, from the model the
// controller returned (`initial`), and once in the browser after hydration. A
// screen that has `initial` renders it straight away; one that does not falls
// back to a client fetch. That is what keeps the server rendering real rather
// than decorative.
import React, { useEffect, useState } from 'react';
import {
  BrowserRouter,
  Link,
  Route,
  Routes,
  StaticRouter,
  useSearchParams,
} from 'react-router';

import { api } from './api';
import { Alert, AuthCard, Field, NotFound, Page } from './components';

function Shell({ user, children }) {
  return (
    <html lang="en">
      <head>
        <meta charSet="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Pyronaut Full Stack</title>
        <link rel="stylesheet" href="/static/css/app.css" />
      </head>
      <body>
        {user ? (
          <nav className="nav">
            <Link className="brand" to="/">
              Pyronaut Full Stack
            </Link>
            <div className="nav-links">
              <Link to="/">Dashboard</Link>
              <Link to="/items">Items</Link>
              <Link to="/settings">Settings</Link>
              {user.isSuperuser ? <Link to="/admin">Admin</Link> : null}
              <form method="post" action="/api/v1/logout" className="logout">
                <button type="submit" data-testid="logout-button">
                  Log out
                </button>
              </form>
            </div>
          </nav>
        ) : null}
        <main>{children}</main>
      </body>
    </html>
  );
}

// ---------------------------------------------------------------- auth ----
function Login({ initial }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(initial?.error ? 'Incorrect email or password' : null);
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.login(email, password);
      // A real navigation, not a client-side one. Signing in changes who the
      // session belongs to, and the server renders the shell and the initial
      // model for the authenticated user. Routing client-side would leave the
      // app showing signed-out chrome until something else refreshed it.
      window.location.assign('/');
    } catch (failure) {
      setError(failure.status === 401 ? 'Incorrect email or password' : failure.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard
      title="Log in"
      footer={
        <>
          <Link to="/signup">Create an account</Link>
          <Link to="/recover-password">Forgot your password?</Link>
        </>
      }
    >
      <form onSubmit={submit}>
        <Alert kind="error">{error}</Alert>
        <Field id="email" label="Email" type="email" value={email} onChange={setEmail} required />
        <Field
          id="password"
          label="Password"
          type="password"
          value={password}
          onChange={setPassword}
          required
        />
        <button className="button" type="submit" disabled={busy} data-testid="login-submit">
          {busy ? 'Logging in…' : 'Log In'}
        </button>
      </form>
    </AuthCard>
  );
}

function Signup() {
  const [form, setForm] = useState({ fullName: '', email: '', password: '' });
  const [error, setError] = useState(null);
  const [errors, setErrors] = useState({});
  const set = (key) => (value) => setForm((current) => ({ ...current, [key]: value }));

  async function submit(event) {
    event.preventDefault();
    setError(null);
    setErrors({});
    try {
      await api.signup(form);
      await api.login(form.email, form.password);
      window.location.assign('/');
    } catch (failure) {
      setError(failure.message);
      setErrors(failure.errors);
    }
  }

  return (
    <AuthCard title="Create an account" footer={<Link to="/login">Already registered? Log in</Link>}>
      <form onSubmit={submit}>
        <Alert kind="error">{error}</Alert>
        <Field
          id="fullName"
          label="Full name"
          value={form.fullName}
          onChange={set('fullName')}
          error={errors.fullName}
        />
        <Field
          id="email"
          label="Email"
          type="email"
          value={form.email}
          onChange={set('email')}
          error={errors.email}
          required
        />
        <Field
          id="password"
          label="Password"
          type="password"
          value={form.password}
          onChange={set('password')}
          error={errors.password}
          required
        />
        <button className="button" type="submit" data-testid="signup-submit">
          Sign Up
        </button>
      </form>
    </AuthCard>
  );
}

function RecoverPassword() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);

  async function submit(event) {
    event.preventDefault();
    await api.recoverPassword(email).catch(() => {});
    // The API answers identically whether or not the address is registered, so
    // the screen must not reveal the difference either.
    setSent(true);
  }

  return (
    <AuthCard title="Password recovery" footer={<Link to="/login">Back to log in</Link>}>
      {sent ? (
        <Alert kind="success">
          If that email is registered, we have sent a password recovery link.
        </Alert>
      ) : (
        <form onSubmit={submit}>
          <Field id="email" label="Email" type="email" value={email} onChange={setEmail} required />
          <button className="button" type="submit" data-testid="recover-submit">
            Send recovery link
          </button>
        </form>
      )}
    </AuthCard>
  );
}

function ResetPassword({ initial }) {
  const [params] = useSearchParams();
  const token = initial?.token ?? params.get('token') ?? '';
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError(null);
    try {
      await api.resetPassword({ token, newPassword: password });
      setDone(true);
    } catch (failure) {
      setError(failure.message);
    }
  }

  return (
    <AuthCard title="Set a new password" footer={<Link to="/login">Back to log in</Link>}>
      {done ? (
        <Alert kind="success">Your password has been updated. You can now log in.</Alert>
      ) : (
        <form onSubmit={submit}>
          <Alert kind="error">{error}</Alert>
          <Field
            id="new-password"
            label="New password"
            type="password"
            value={password}
            onChange={setPassword}
            required
          />
          <button className="button" type="submit" data-testid="reset-submit">
            Reset password
          </button>
        </form>
      )}
    </AuthCard>
  );
}

// ----------------------------------------------------------- dashboard ----
function Dashboard({ initial }) {
  const [user, setUser] = useState(initial?.user);
  useEffect(() => {
    if (!user) api.me().then(setUser).catch(() => {});
  }, []);
  return (
    <Page title={`Hi, ${user?.fullName || user?.email || 'there'}`}>
      <p>Welcome back. This page was rendered on the server and hydrated in your browser.</p>
      <Link className="button" to="/items">
        Manage items
      </Link>
    </Page>
  );
}

// --------------------------------------------------------------- items ----
function Items({ initial }) {
  const [state, setState] = useState({
    items: initial?.items,
    count: initial?.count ?? 0,
    loading: !initial?.items,
    error: null,
  });
  const [draft, setDraft] = useState({ title: '', description: '' });

  async function reload() {
    try {
      const page = await api.items();
      setState({ items: page.data, count: page.count, loading: false, error: null });
    } catch (error) {
      setState((current) => ({ ...current, loading: false, error }));
    }
  }

  useEffect(() => {
    if (!initial?.items) reload();
    // Intentionally runs once: the server already supplied the first page.
  }, []);

  async function add(event) {
    event.preventDefault();
    await api.createItem(draft);
    setDraft({ title: '', description: '' });
    await reload();
  }

  async function remove(id) {
    await api.deleteItem(id);
    await reload();
  }

  if (state.loading) return <Page title="Items">Loading…</Page>;

  return (
    <Page title="Items">
      <Alert kind="error">{state.error?.message}</Alert>
      <form className="inline-form" onSubmit={add}>
        <Field
          id="title"
          label="Title"
          value={draft.title}
          onChange={(value) => setDraft((d) => ({ ...d, title: value }))}
          required
        />
        <Field
          id="description"
          label="Description"
          value={draft.description}
          onChange={(value) => setDraft((d) => ({ ...d, description: value }))}
        />
        <button className="button" type="submit" data-testid="add-item">
          Add item
        </button>
      </form>
      {state.items?.length ? (
        <table data-testid="items-table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Description</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {state.items.map((item) => (
              <tr key={item.id}>
                <td>{item.title}</td>
                <td>{item.description || '—'}</td>
                <td>
                  <button type="button" onClick={() => remove(item.id)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p>You have no items yet.</p>
      )}
    </Page>
  );
}

// ------------------------------------------------------------ settings ----
function Settings({ initial }) {
  const [profile, setProfile] = useState({
    fullName: initial?.user?.fullName || '',
    email: initial?.user?.email || '',
  });
  const [saved, setSaved] = useState(null);
  useEffect(() => {
    if (initial?.user) return;
    api
      .me()
      .then((user) => setProfile({ fullName: user.fullName || '', email: user.email || '' }))
      .catch(() => {});
  }, []);

  async function save(event) {
    event.preventDefault();
    await api.updateMe(profile);
    setSaved('Your profile has been updated.');
  }

  return (
    <Page title="Settings">
      <Alert kind="success">{saved}</Alert>
      <form onSubmit={save}>
        <Field
          id="fullName"
          label="Full name"
          value={profile.fullName}
          onChange={(value) => setProfile((p) => ({ ...p, fullName: value }))}
        />
        <Field
          id="email"
          label="Email"
          type="email"
          value={profile.email}
          onChange={(value) => setProfile((p) => ({ ...p, email: value }))}
        />
        <button className="button" type="submit" data-testid="save-profile">
          Save
        </button>
      </form>
    </Page>
  );
}

// --------------------------------------------------------------- admin ----
function Admin({ initial }) {
  const [users, setUsers] = useState(initial?.users);
  useEffect(() => {
    if (!users) api.users().then((page) => setUsers(page.data)).catch(() => setUsers([]));
  }, []);
  if (!users) return <Page title="Users">Loading…</Page>;
  return (
    <Page title="Users">
      <table data-testid="users-table">
        <thead>
          <tr>
            <th>Email</th>
            <th>Full name</th>
            <th>Role</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <tr key={user.id}>
              <td>{user.email}</td>
              <td>{user.fullName || '—'}</td>
              <td>{user.isSuperuser ? 'Superuser' : 'User'}</td>
              <td>{user.isActive ? 'Active' : 'Inactive'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Page>
  );
}

// --------------------------------------------------------------- routes ---
export function App(props) {
  const { page, data = {}, url } = props || {};
  // The server model belongs to exactly one screen; every other screen fetches.
  const on = (name) => (page === name ? data : null);
  const Router = typeof window === 'undefined' ? StaticRouter : BrowserRouter;

  // Who is signed in is a property of the session, not of whichever screen the
  // server happened to render. Taking it from `data.user` meant the navigation
  // disappeared the moment you navigated client-side away from the screen that
  // supplied it. On the server there is no effect to run, so the model's user
  // is used as-is; in the browser it is confirmed against the API.
  const [user, setUser] = useState(data.user);
  useEffect(() => {
    if (user) return;
    api
      .me()
      .then(setUser)
      .catch(() => setUser(null));
  }, []);
  const routerProps = typeof window === 'undefined' ? { location: url || '/' } : {};

  // The router wraps the shell, not the other way round: the navigation links
  // in Shell need the router context too, and a router renders only a context
  // provider, so it emits no markup around <html>.
  return (
    <Router {...routerProps}>
      <Shell user={user}>
        {/*
          Every route is explicit, and each screen is handed the server model
          only when the server actually rendered that screen. A catch-all that
          dispatched on the server's `page` prop would re-render the first
          screen on every client-side navigation — signing in would leave you
          looking at the login form, at the dashboard's URL.

          Where `initial` is null the screen fetches for itself, which is what
          makes client-side navigation work at all.
        */}
        <Routes>
          <Route path="/login" element={<Login initial={on('login')} />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/recover-password" element={<RecoverPassword />} />
          <Route path="/reset-password" element={<ResetPassword initial={on('resetPassword')} />} />
          <Route path="/" element={<Dashboard initial={on('dashboard')} />} />
          <Route path="/items" element={<Items initial={on('items')} />} />
          <Route path="/settings" element={<Settings initial={on('settings')} />} />
          <Route path="/admin" element={<Admin initial={on('admin')} />} />
          <Route path="*" element={<NotFound message={data?.message} />} />
        </Routes>
      </Shell>
    </Router>
  );
}
