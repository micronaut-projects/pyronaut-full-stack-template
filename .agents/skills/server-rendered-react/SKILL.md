---
name: server-rendered-react
description: Add or change screens in a Micronaut Views React application that server-renders on GraalJS and hydrates in the browser. Use when users add a page, change routing, touch session or navigation state, or report that a page renders correctly but does not work once loaded.
license: Apache-2.0
compatibility: Projects using micronaut-views-react with a webpack SSR bundle and a browser hydration bundle
metadata:
  author: micronaut-projects/pyronaut-full-stack-template
  version: "1.0.0"
---

# Server-rendered React

The server renders the React tree on GraalJS and sends complete HTML; the browser then hydrates the same tree. Both halves have to be right, and only one of them is visible in a response body.

## Goal

Add screens that work identically whether the server rendered them or the browser navigated to them — and catch the failures where the HTML is perfect and the application is inert.

## Trigger Examples

Should trigger:

- "Add a settings page to this app."
- "The page renders but clicking does nothing."
- "Signing in leaves me on the login screen."
- "The navigation disappears when I navigate."

Should not trigger:

- Client-only React projects with no server rendering.
- Styling-only changes with no routing or data involved.

## The central trap

**The server sends the model for exactly one screen.** Treating that model as if it described the whole application is the mistake this architecture invites, and it is invisible in a response body because the server-rendered first paint is always correct.

Four ways it shows up, all observed in practice:

- A catch-all route dispatching on the server's `page` prop, so every client-side navigation re-renders whichever screen the server sent first.
- Screens that only render from `initial` and have no fetch to fall back on, so they are blank when reached client-side.
- Navigation chrome reading the signed-in user from the page model, so it disappears when you navigate away from the screen that supplied it.
- A session lookup in an effect with `[]` dependencies that runs once while signed out and never again.

Each leaves `curl` entirely satisfied.

## Procedure

1. Add the route explicitly.
2. Give the screen a fetch path.
3. Take session state from the shell, not the page model.
4. Test it by navigating to it, not by loading it.

### 1) Add the route explicitly

Never use a catch-all that selects a component from the server's `page` prop. Route on the URL, and pass the server model only when the server actually rendered that screen:

```jsx
const on = (name) => (page === name ? data : null);

<Route path="/settings" element={<Settings initial={on('settings')} />} />
```

### 2) Give the screen a fetch path

`initial` is null whenever the user arrived client-side. Every screen needs to cope:

```jsx
function Settings({ initial }) {
  const [user, setUser] = useState(initial?.user);
  useEffect(() => {
    if (!user) api.me().then(setUser).catch(() => {});
  }, []);
  ...
}
```

A screen that renders only from `initial` works on first load and is blank forever after.

### 3) Take session state from the shell, not the page model

Who is signed in is a property of the session, not of the rendered screen. Hold it once, above the routes, seeded from the server model and confirmed against the API in the browser.

Identity changes belong to the server: after signing in, do a **real** navigation rather than a client-side one.

```js
await api.login(email, password);
window.location.assign('/');
```

The server then renders the authenticated shell and the initial model. Routing client-side across an identity change means rebuilding on the client what the server already knows, and is the direct cause of the third and fourth failures listed above.

### 4) Test it by navigating to it, not by loading it

A browser test that calls `page.navigate('/settings')` exercises the server path only, and will pass while client-side navigation is completely broken. The test has to arrive the way a user does:

```python
_sign_in(page)                      # a real transition
page.click("a[href='/settings']")   # a client-side navigation
```

Also assert the hydration bundle is actually served. If `/static/client.js` 404s or 401s, pages render perfectly and are inert; forms fall back to native submits and the symptom is a mysterious navigation timeout rather than an obvious error.

```python
assert page.request().get(f"{base_url}/static/client.js").status() == 200
```

Static resources are subject to the security filter. Permit them explicitly:

```toml
[[micronaut.security.intercept-url-map]]
pattern = '/static/**'
access = ['isAnonymous()']
```

## Bundle mechanics

One webpack bundle holds every render root — the page tree and any email components — because `server-bundle-path` is a single setting. Export each root from the SSR entry point.

GraalJS lacks browser globals React's server renderer expects: `URL`, `URLSearchParams`, `TextEncoder`/`TextDecoder` and web streams all need polyfilling in the server bundle only.

The bundles are generated and not committed, so `npm run build` must precede `pyronaut dev` and `pyronaut test`. Without them every server-rendered route returns 500.

## Verification

```bash
npm run check   # unit tests, both bundles, and a render check over every root
pyronaut test   # the browser suite, which is the only thing that sees hydration
```

Adding a render root means adding a case to the server-render smoke check as well as a browser test.
