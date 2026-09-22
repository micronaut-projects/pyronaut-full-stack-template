# Pyronaut Full-Stack Template — Implementation Plan

A port of [`fastapi/full-stack-fastapi-template`](https://github.com/fastapi/full-stack-fastapi-template)
to [Pyronaut](https://github.com/micronaut-projects/pyronaut), built to showcase what the Micronaut
programming model gives a Python developer that FastAPI cannot.

**Status:** draft for review. Nothing has been implemented yet.

---

## 1. Purpose and success criteria

This is not just a rewrite. The FastAPI template is the reference implementation of "a serious
Python web app"; the point of the port is that the same application, written in the same language,
comes out **smaller, faster, and with fewer moving parts** on Pyronaut.

Success criteria, in priority order:

1. **Feature parity.** Every user-visible feature of the FastAPI template works (§2).
2. **Fewer moving parts.** The FastAPI template's local stack is five containers wired by Docker
   Compose (Traefik, Postgres, Adminer, backend, frontend) plus a Vite dev server. Ours is
   `pyronaut dev` plus containers that Test Resources starts on demand. No `docker compose up`.
3. **One deployable.** One artifact serves the API *and* server-renders the React app. No separate
   frontend container, no reverse proxy needed to glue them.
4. **A credible performance story.** Native image startup and memory numbers, and a concurrency
   story that does not depend on running N worker processes (§4.3).
5. **The showcase is legible.** A reader should be able to open one file and see why the Micronaut
   version is better, not have to take our word for it.

### 1.1 The advantages we are actually demonstrating

| Advantage | Where it shows up in this template |
| --- | --- |
| No GIL bottleneck | GraalPy context pooling gives true parallelism for Python request handling in one process — no gunicorn worker fleet. Verified: `pyronaut/src/main/docs/guide/concepts/threading/contextPool.adoc`. |
| Compile-time DI and validation | Beans, routes, repositories and constraints are resolved during `pyronaut process`, not at import time. Wiring mistakes are build failures. |
| Declarative data access | Micronaut Data JDBC generates SQL from method names at build time. No ORM session lifecycle, no lazy-loading surprises, no N+1 by accident. |
| No Pydantic problem | Pyronaut's own docs state Pydantic "does not work reliably in Pyronaut's multithreaded scenarios" (`usingPackagesJavaLibraries.adoc`). Micronaut Validation + Serde replace it with build-time-generated code. |
| The JVM ecosystem, one import away | MySQL JDBC, Flyway, Jakarta Mail, Playwright, Testcontainers — all `pip`-free imports. |
| Server-side React without Node in production | Micronaut Views React runs the SSR bundle on GraalJS inside the same JVM. Node is a build-time dependency only. |
| Real integration tests, no Compose | Test Resources starts MySQL; Testcontainers starts Mailpit. `pyronaut test` is the whole command. |
| Native image | `pyronaut build --native --docker` produces a container that starts in milliseconds. |
| Drop to Java when it pays | `src-java/` compiles alongside Python in the same DI container (`projectStructure.adoc`). |

---

## 2. Parity inventory — what the FastAPI template actually contains

Taken from the current `main` of the upstream template.

### 2.1 Backend API surface

| Endpoint | Auth | Notes |
| --- | --- | --- |
| `POST /api/v1/login/access-token` | anonymous | OAuth2 password form → bearer token |
| `POST /api/v1/login/test-token` | user | returns current user |
| `POST /api/v1/password-recovery/{email}` | anonymous | sends reset email; response is constant to prevent enumeration |
| `POST /api/v1/reset-password/` | anonymous | token + new password |
| `POST /api/v1/password-recovery-html-content/{email}` | superuser | returns the email HTML |
| `GET /api/v1/users/` | superuser | paginated (`skip`, `limit`), returns `{data, count}` |
| `POST /api/v1/users/` | superuser | creates user, optionally emails them |
| `GET /api/v1/users/me` | user | |
| `PATCH /api/v1/users/me` | user | |
| `PATCH /api/v1/users/me/password` | user | |
| `DELETE /api/v1/users/me` | user | superuser may not delete self |
| `POST /api/v1/users/signup` | anonymous | open registration |
| `GET /api/v1/users/{user_id}` | user | non-superusers may only read themselves |
| `PATCH /api/v1/users/{user_id}` | superuser | |
| `DELETE /api/v1/users/{user_id}` | superuser | cascades to items |
| `GET /api/v1/items/` | user | paginated; superuser sees all, user sees own |
| `GET /api/v1/items/{id}` | user | ownership-checked |
| `POST /api/v1/items/` | user | |
| `PUT /api/v1/items/{id}` | user | |
| `DELETE /api/v1/items/{id}` | user | |
| `POST /api/v1/utils/test-email/` | superuser | |
| `GET /api/v1/utils/health-check/` | anonymous | |
| `POST /api/v1/private/users/` | dev env only | test fixture helper |

### 2.2 Domain model

`User` (uuid PK, unique indexed email, hashed_password, is_active, is_superuser, full_name,
created_at) and `Item` (uuid PK, title, description, created_at, owner_id FK → user, ON DELETE
CASCADE). Response wrappers `UsersPublic`/`ItemsPublic` carry `{data, count}`.

### 2.3 Everything else

- **Frontend:** React 19, Vite 8, TanStack Router (file-based, generated route tree), TanStack
  Query, TanStack Table, shadcn/ui on Radix, Tailwind v4, react-hook-form + zod, axios, Biome, Bun.
- **Generated API client:** backend OpenAPI JSON → `@hey-api/openapi-ts` → typed TS SDK.
- **Screens:** login, signup, recover password, reset password, dashboard, items CRUD with a data
  table, user settings (profile, password, appearance/dark mode, delete account), admin user CRUD.
- **Email:** Jinja templates authored as React Email components (`packages/react-email`), sent via
  SMTP, captured by Mailpit in dev.
- **Migrations:** Alembic, five revisions.
- **Tests:** pytest for the backend, Playwright (TypeScript) for the frontend.
- **CI:** GitHub Actions — backend tests, Playwright, docker-compose smoke test, pre-commit, coverage.
- **Local stack:** Docker Compose — Traefik, Postgres, Adminer, backend, frontend, Mailpit.
- **Deployment:** Compose + Traefik with Let's Encrypt, plus docs.
- **Template mechanics:** Copier template with `hooks/post_gen_project.py` and `.env`-driven config.

---

## 3. Technology mapping

| FastAPI template | Pyronaut template | Status |
| --- | --- | --- |
| FastAPI + Starlette | Micronaut HTTP (Netty) via Pyronaut decorators | Verified in petclinic |
| SQLModel / SQLAlchemy | Micronaut Data JDBC (`@MappedEntity`, `CrudRepository`, `Protocol` repos) | Verified in petclinic |
| Postgres | **MySQL** — `com.mysql:mysql-connector-j`, `Dialect.MYSQL` | Verified: `pyronaut/src/main/docs/examples/direct-source/mysql/App.java` |
| Alembic | Micronaut Flyway + `flyway-mysql` | Flyway verified in petclinic (Oracle) |
| Pydantic (validation) | Micronaut Validation — `jakarta.validation.constraints.*` via `Annotated` | Verified in petclinic `forms.py` |
| Pydantic (serialization) | Micronaut Serialization — `@Serdeable` | Verified in petclinic |
| pydantic-settings / `.env` | Micronaut `@ConfigurationProperties` + `application.toml` + env vars | To build |
| python-jose / PyJWT + OAuth2PasswordBearer | **Micronaut Security JWT** — `HttpRequestAuthenticationProvider`, `@Secured` | **Verified: `micronaut-security/test-suite-python/`** |
| pwdlib (argon2/bcrypt) | JVM hashing library (§7.3) | Decision needed |
| `emails` + SMTP | **Micronaut Email** — `micronaut-email-javamail` | Verified: `micronaut-email` module list |
| Jinja email templates | `micronaut-email-template` (`TemplateBody`) over a Micronaut Views engine | Verified module exists |
| Mailpit via Compose | Mailpit via Testcontainers + **`micronaut-email-mailpit-http-client`** for assertions | Verified: `micronaut-email/test-suite/.../OrderServiceTest.java` |
| Vite SPA in its own container | **Micronaut Views React** SSR + hydration, served by the app | Verified in petclinic |
| FastAPI `/openapi.json` | Pyronaut generates OpenAPI from routes and dataclasses, serves Swagger UI and ReDoc | Verified: `concepts/httpApis.adoc` |
| Playwright (TypeScript) | **Playwright Java** (`com.microsoft.playwright:playwright`) driven from pytest | **No precedent — spike required (§11.2)** |
| Docker Compose for dev | **Test Resources** (MySQL) + Testcontainers (Mailpit) | Verified |
| Docker Compose + Traefik for deploy | `pyronaut build --jvm --docker` / `--native --docker` | Verified: `packaging.adoc` |
| `setup-python` + `uv` in CI | **`micronaut-projects/setup-pyronaut`** | **Action not yet released — see §11.1** |

---

## 4. Target architecture

### 4.1 One process, three responsibilities

```
                ┌──────────────────────── JVM ────────────────────────┐
  browser ──────▶  Netty HTTP server                                  │
                │    ├── /api/v1/**   JSON controllers  (GraalPy)     │
                │    ├── /**          React SSR routes  (GraalPy →    │
                │    │                 Micronaut Views React → GraalJS)│
                │    └── /static/**   hydration bundle + assets        │
                │                                                      │
                │  Micronaut DI container                              │
                │    ├── Python beans   (services, controllers)        │
                │    ├── Java beans     (src-java/, where needed)      │
                │    └── Generated      (Data repositories, Serde,     │
                │                        Validation, Security)         │
                └───────────┬──────────────────────┬──────────────────┘
                            │ JDBC                 │ SMTP
                        ┌───▼────┐            ┌────▼────┐
                        │ MySQL  │            │ Mailpit │   ← dev/test only:
                        └────────┘            └─────────┘     started by Test
                                                              Resources /
                                                              Testcontainers
```

Python and JavaScript run in the same JVM in separate polyglot contexts — the petclinic proves this
combination works.

### 4.2 The SSR decision, and what it costs

The upstream template is a **pure SPA**: Vite serves the frontend, the browser fetches an empty
shell, TanStack Router renders client-side, and auth state lives in `localStorage`.

We are going **SSR-first** (the explicit requirement, and the more interesting demo). Consequences
that must be designed for, not discovered:

1. **Auth must move to a cookie.** SSR runs on the server and cannot read `localStorage`. To
   server-render an authenticated page we need the token on the request. Micronaut Security
   supports `micronaut.security.authentication = cookie` with JWT in an HttpOnly cookie. This is
   strictly better security than the upstream's `localStorage` bearer token — worth calling out in
   the README — but it changes the login flow and the Playwright `storageState` setup.
2. **No Vite dev server.** `pyronaut dev` serves everything; the JS watcher runs alongside
   (`npm run watch`, as in the petclinic). We lose Vite HMR and get webpack watch + browser reload.
   This is a real developer-experience regression versus upstream and should be acknowledged.
3. **Two bundles.** `webpack.server.cjs` → `views/ssr-components.mjs`, `webpack.client.cjs` →
   `static/client.js`. Neither is committed.
4. **Route duplication.** Every SSR route needs a Python controller returning
   `ModelAndView("App", {...})` *and* a client route in the React tree. The petclinic shows the
   pattern; we should factor it so the two stay in sync.

### 4.3 Concurrency story

`micronaut.python.pool` is the headline. The FastAPI template scales by running multiple uvicorn
workers behind Traefik; we run one process with N GraalPy contexts and real parallelism. The
README should show this concretely (a `/api/v1/utils/health-check/`-style CPU benchmark under load,
FastAPI vs. Pyronaut, same machine).

---

## 5. Repository layout

```
pyronaut-full-stack-template/
├── pyproject.toml              Pyronaut project + Java deps + source layout
├── package.json                React build (webpack, babel, jest) + Biome
├── webpack.server.cjs          → views/ssr-components.mjs   (GraalJS SSR bundle)
├── webpack.client.cjs          → static/client.js           (hydration bundle)
├── biome.json
├── src/                        Python application sources
│   └── app/
│       ├── entities.py         @MappedEntity dataclasses (User, Item)
│       ├── dto.py              @Serdeable request/response DTOs + constraints
│       ├── repositories.py     @JdbcRepository Protocol repositories
│       ├── services/
│       │   ├── users.py        UserService  (CRUD, password hashing)
│       │   ├── items.py        ItemService
│       │   └── mail.py         MailService  (Micronaut Email)
│       ├── security/
│       │   ├── provider.py     HttpRequestAuthenticationProvider
│       │   ├── tokens.py       password-reset token issue/verify
│       │   └── claims.py       roles + user id claims
│       ├── controllers/
│       │   ├── login.py        /api/v1/login/**, password recovery
│       │   ├── users.py        /api/v1/users/**
│       │   ├── items.py        /api/v1/items/**
│       │   ├── utils.py        /api/v1/utils/**
│       │   ├── private.py      @Requires(env="dev")
│       │   └── views.py        SSR routes → ModelAndView("App", ...)
│       ├── config.py           @ConfigurationProperties (app.*)
│       └── bootstrap.py        StartupEvent listener → first superuser
├── src-java/                   Java escape hatch (expected: empty or near-empty)
├── config/
│   ├── application.toml
│   ├── application-dev.toml
│   └── db/migration/           Flyway V1__… (MySQL)
├── frontend/
│   ├── client.jsx              hydrateRoot
│   ├── server.jsx              GraalJS polyfills + exports
│   └── src/                    routes, components, generated API client
├── static/                     css, images, generated client.js
├── views/                      generated ssr-components.mjs
├── tests/                      pytest — API + integration
│   ├── conftest.py             MicronautTest fixtures, MySQL, Mailpit
│   ├── test_login.py
│   ├── test_users.py
│   ├── test_items.py
│   ├── test_email.py           asserts via MailpitClient
│   └── e2e/                    Playwright Java driven from pytest
├── tests-config/
│   └── application-test.toml
├── test-java/                  Java test escape hatch
└── .github/workflows/ci.yml    setup-pyronaut
```

---

## 6. `pyproject.toml` (proposed)

```toml
[project]
name = "pyronaut-full-stack-template"
version = "0.1.0"

[tool.pyronaut.toolchain]
type = "jvm"

[tool.pyronaut]
repositories = ["mavenCentral"]
core.version = "<pin>"
platform.version = "<pin>"

[tool.pyronaut.sources]
python = "src"
python-test = "tests"
java = "src-java"
java-test = "test-java"
resources = "config"
test-resources = "tests-config"
additional-resources = ["views", "static"]

[tool.pyronaut.test-resources]
enabled = true
additional-modules = ["jdbc-mysql"]
client-timeout = 180

[tool.pyronaut.dependencies]
runtime = [
  "io.micronaut:micronaut-http-server-netty",
  "io.micronaut.data:micronaut-data-jdbc",
  "io.micronaut.sql:micronaut-jdbc-hikari",
  "com.mysql:mysql-connector-j",
  "io.micronaut.flyway:micronaut-flyway",
  "org.flywaydb:flyway-mysql",
  "io.micronaut.serde:micronaut-serde-jackson",
  "io.micronaut.validation:micronaut-validation",
  "io.micronaut.security:micronaut-security-jwt",
  "io.micronaut.email:micronaut-email-javamail",
  "io.micronaut.email:micronaut-email-template",
  "org.eclipse.angus:angus-mail",
  "io.micronaut.views:micronaut-views-react",
  "org.graalvm.polyglot:polyglot",
  "org.graalvm.polyglot:js",
  "at.favre.lib:bcrypt",                       # §7.3 — decision pending
  "io.micronaut.pyronaut:micronaut-pyronaut-logback",
]
build = [
  "io.micronaut:micronaut-context-python",
  "io.micronaut:micronaut-inject-python",
  "io.micronaut.data:micronaut-data-processor",
  "io.micronaut.serde:micronaut-serde-processor",
  "io.micronaut.validation:micronaut-validation-processor",
  "io.micronaut.security:micronaut-security-annotations",
  "io.micronaut.openapi:micronaut-openapi",     # §11.6 — verify needed/bundled
]
test = [
  "io.micronaut.pyronaut:micronaut-pyronaut-pytest",
  "io.micronaut.pyronaut:micronaut-pyronaut-requests",
  "io.micronaut.test:micronaut-test-junit5",
  "io.micronaut.testresources:micronaut-test-resources-jdbc-mysql",
  "io.micronaut.email:micronaut-email-mailpit-http-client",
  "org.testcontainers:testcontainers",
  "com.microsoft.playwright:playwright",
]
```

Exact versions to be pinned once the Micronaut Platform version is chosen. Modules managed by the
platform BOM use versionless coordinates.

---

## 7. Backend design

### 7.1 Entities and schema

Two `@MappedEntity` dataclasses mirroring upstream. Design points:

- **UUID primary keys on MySQL.** MySQL has no native UUID type. Options: `BINARY(16)` (compact,
  indexes well, ugly in `SELECT`) or `CHAR(36)` (readable, 2.25× the bytes). **Recommendation:
  `CHAR(36)`** with `@AutoPopulated` — the template's job is to be read, not to win benchmarks, and
  a readable `users` table matters more here. Flag for review.
- **Cascade delete.** Upstream relies on SQLModel `cascade_delete=True`. Micronaut Data JDBC does
  not cascade deletes. We declare `ON DELETE CASCADE` in the Flyway migration and let the database
  enforce it — arguably the more honest implementation, and worth a comment in the migration.
- **`created_at`.** `@DateCreated` replaces the `default_factory` pattern.
- **Unique email index** in the migration.

### 7.2 DTOs, validation, serialization

`@Serdeable` dataclasses with `Annotated[..., NotBlank, Size, Email]`. Micronaut Validation runs
constraints at the controller boundary via `@Valid`, so — unlike the petclinic, which calls the
`Validator` bean by hand — we should use declarative `@Valid` on `@Body` parameters and map
`ConstraintViolationException` to the upstream error shape with an exception handler. That gives us
one place to control the API error contract.

**Open question:** upstream returns FastAPI's `{"detail": ...}` shape and the generated TS client
expects it. We should match it exactly so the frontend port is mechanical.

### 7.3 Password hashing — decision needed

Upstream uses `pwdlib` with Argon2 primary and bcrypt fallback, and `verify_and_update` to rehash
on login. Micronaut Security does not ship a password encoder. Candidates:

| Option | Pros | Cons |
| --- | --- | --- |
| `at.favre.lib:bcrypt` | Tiny, zero deps, pure Java, native-image friendly | bcrypt only; no Argon2 |
| `de.mkammerer:argon2-jvm` | Matches upstream's primary | Bundles a JNI native lib — **likely a problem for GraalVM native image** |
| `org.springframework.security:spring-security-crypto` | Argon2 + bcrypt + pbkdf2, pure Java, no Spring runtime | Pulling a Spring artifact into a Micronaut showcase reads badly |
| `org.bouncycastle` | Argon2 in pure Java, well-trusted | Large dependency |

**Recommendation: `at.favre.lib:bcrypt`**, with an `PasswordEncoder` abstraction (Python ABC) so
swapping in Argon2 is a one-file change. Rationale: native-image compatibility is a headline
feature of this template and a JNI dependency would undermine it. **Needs sign-off.**

### 7.4 Security

Verified against `micronaut-security/test-suite-python`, so this is low-risk:

- `HttpRequestAuthenticationProvider` subclassed in Python; `authenticate()` looks up the user by
  email, verifies the hash, returns `AuthenticationResponse.success(id, roles, claims)`.
- Roles: `ROLE_USER`, `ROLE_SUPERUSER`. `@Secured(["ROLE_SUPERUSER"])` replaces upstream's
  `Depends(get_current_active_superuser)`.
- `Authentication` injected as a controller parameter replaces `CurrentUser`.
- Ownership checks (a user may read their own record; a user may only touch their own items) are
  not expressible as roles — they stay as explicit service-layer checks, same as upstream.
- **Login endpoint mismatch:** Micronaut Security's `/login` takes JSON
  `{"username","password"}`; upstream's `/api/v1/login/access-token` takes an OAuth2
  `application/x-www-form-urlencoded` form and returns `{"access_token","token_type"}`. We
  configure `micronaut.security.endpoints.login.path` and add a thin compatibility controller, or
  accept the Micronaut shape and regenerate the TS client. **Recommendation: keep the Micronaut
  shape** — the client is generated from OpenAPI anyway, so there is no reason to carry FastAPI's
  OAuth2 form quirk. Flag for review.
- **Cookie vs bearer:** see §4.2. Recommendation is `cookie` authentication mode so SSR works,
  with refresh-token support enabled.
- Password-reset tokens: a separate short-lived signed JWT with a `purpose: reset` claim, issued
  and validated by our own bean rather than reusing the access-token generator.

### 7.5 Email

- `EmailSender` injected into a Python `MailService`.
- Templates via `micronaut-email-template` `TemplateBody`.
- **Opportunity:** since `micronaut-email-template` renders through Micronaut Views, and we already
  have Micronaut Views React configured, the email templates could be **React components rendered
  on GraalJS** — a direct analogue of upstream's `packages/react-email`, with no Node at runtime.
  This would be the single most impressive thing in the template. **Unverified** whether
  `views-react` satisfies the `TemplateBody` contract; see §11.7. Fallback: Velocity or Thymeleaf
  templates, which is a parity regression versus upstream's React Email.
- Dev/test send to Mailpit over SMTP via `javamail.properties.mail.smtp.*`.

### 7.6 Configuration

`@ConfigurationProperties("app")` Python class replacing `pydantic-settings`, plus
`application.toml` and environment variables. Upstream's "refuse to boot if SECRET_KEY is still
`changethis`" check maps to a `@PostConstruct` validation in the config bean — keep it, it is a good
idea.

We should ship a `.env`-compatible story since the Copier template and the docs lean on it heavily.
Micronaut reads env vars natively; a `.env` file needs either a small loader or documented
`export`/`direnv` usage. **Open question** (§12).

### 7.7 Bootstrap

`ApplicationEventListener[StartupEvent]` in Python creates the first superuser from configuration,
replacing `initial_data.py` and the `prestart.sh` hook.

---

## 8. Frontend design

### 8.1 The hard part

The upstream frontend is React 19 + Vite 8 + Tailwind v4 + TanStack Router (file-based codegen) +
shadcn/Radix. The petclinic's proven SSR configuration is React **18.2** + webpack + hand-written
polyfills (`web-streams-polyfill`, `text-encoding`, and locally defined `URL`/`URLSearchParams`
because GraalJS does not provide them).

Porting the whole upstream stack onto GraalJS SSR in one step is the largest risk in this plan
(§11.3). The plan therefore stages it:

**Stage A — prove the stack.** Port the *screens* to the petclinic's proven SSR setup: React 18,
webpack, react-router. Plain CSS or a CDN stylesheet. Get every route server-rendering and
hydrating, with the generated API client. This is a working template.

**Stage B — modernise, one axis at a time,** each behind its own spike:
1. Tailwind v4 (build-time only — lowest risk).
2. shadcn/Radix components (SSR-safe, but `useLayoutEffect` warnings and portal behaviour need checking).
3. React 19 SSR on GraalJS (highest risk — new streaming internals, `react-dom/server.browser` surface).
4. TanStack Router with SSR (its SSR story is newer than react-router's; file-based codegen adds a build step).

Stage A is the deliverable; Stage B items ship as they pass. **A template that ships with React 18
and works is worth more than one that targets React 19 and does not.**

### 8.2 Generated API client

`pyronaut process` produces an OpenAPI description. Pipeline:

```
pyronaut process → openapi.json → @hey-api/openapi-ts → frontend/src/client/
```

This preserves the best ergonomic feature of the upstream template. **Requires verification that the
generated spec is complete and accurate enough** (schemas for `@Serdeable` dataclasses, security
schemes, operation ids/tags that produce sensible method names) — §11.6.

### 8.3 SSR/CSR data flow

Follow the petclinic: controllers return `{"page": "...", "data": {...}}`; `App` dispatches on
`page`; components render `initial` when present and fall back to a client fetch when not. Every
screen works both ways, which is what makes the hydration real rather than decorative.

---

## 9. Testing strategy

### 9.1 API and integration tests — pytest

`micronaut_test_fixture` + `pyronaut.requests`, as in the petclinic. MySQL comes from Test
Resources; Mailpit from a Testcontainers `GenericContainer` started in a session-scoped fixture,
with its host/port fed into `MicronautTest(properties={...})` — the Python equivalent of the
`TestPropertyProvider` pattern in `micronaut-email`'s own test suite.

Email assertions use `MailpitClient` (`micronaut-email-mailpit-http-client`) — better than
upstream, which does not assert on email contents at all.

**Isolation problem.** Pyronaut's pytest integration explicitly does **not** support per-test
transactions: "`transactional`, `rollback` and `rebuild_context` are accepted for compatibility but
have no effect" (`testing/micronautTest.adoc`). Upstream's suite leans on a transactional session
fixture. Options:

| Option | Assessment |
| --- | --- |
| Explicit cleanup fixture (truncate tables between tests) | Simple, obvious, slightly slow. **Recommended.** |
| Unique data per test (UUID emails/titles), no cleanup | Fast, but leaves the DB dirty and makes count assertions fragile |
| Write the DB-heavy tests as JUnit 5 Python modules | Gets real transactional rollback, but two test styles in one template is confusing |
| Fix it upstream in Pyronaut | Right long-term answer; out of scope here, but worth filing |

### 9.2 End-to-end — Playwright Java from pytest

The requirement is Playwright **Java**, and the test runner is Micronaut's pytest integration. So:

```python
from com.microsoft.playwright import Playwright
from com.microsoft.playwright.options import AriaRole

def test_login(page, base_url):
    page.navigate(f"{base_url}/login")
    page.getByTestId("email-input").fill(superuser_email)
    page.getByTestId("password-input").fill(superuser_password)
    page.getByRole(AriaRole.BUTTON, ...).click()
    page.waitForURL(f"{base_url}/")
```

This is genuinely novel — driving a Java browser-automation API from Python, against a
server-rendered React app, inside the same test session as the API tests. It is also the part with
no precedent anywhere in the repos surveyed (§11.2).

Design notes:
- Session-scoped `Playwright`/`Browser` fixtures; function-scoped `BrowserContext`/`Page`.
- Playwright Java downloads its driver bundle on first `Playwright.create()`; CI must cache it
  (`~/.cache/ms-playwright`) and may need `PLAYWRIGHT_BROWSERS_PATH`.
- Upstream's `auth.setup.ts` + `storageState` maps to `BrowserContext.storageState(...)`; with
  cookie auth (§4.2) this is cleaner than upstream's localStorage dance.
- The app under test is the same embedded server the API tests use — no separate frontend server,
  which removes upstream's `webServer`/`PLAYWRIGHT_BASE_URL` complexity entirely. Good showcase.
- Email-driven flows (password recovery) can be asserted end-to-end: trigger in the browser, read
  the message from `MailpitClient`, extract the link, continue in the browser. Upstream does this
  with a `mailpit.ts` helper; we get it from a supported Micronaut module.

### 9.3 Frontend unit tests

Jest + Testing Library as in the petclinic, run by `npm test`. Kept separate from `pyronaut test`.

---

## 10. CI

One workflow, `.github/workflows/ci.yml`:

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-node@v4
        with: { node-version: '22', cache: npm }
      - run: npm ci
      - run: npm test          # jest
      - run: npm run build     # ssr + client bundles (pyronaut test needs them)
      - uses: micronaut-projects/setup-pyronaut@v1
        with:
          java-version: '25'
          graalvm-version: '25.3'
      - run: pyronaut install
      - run: pyronaut process
      - run: pyronaut test     # pytest: API + Playwright e2e; MySQL and Mailpit via containers
```

Notes:
- Bundle build **must** precede `pyronaut test` — SSR routes fail without `views/ssr-components.mjs`.
- Add a Playwright browser cache step once §11.2 determines the cache path.
- A second job for `pyronaut build --native --docker` to keep the native story honest, probably
  nightly rather than per-PR.
- No `docker compose` job — that is the point.

---

## 11. Gaps, risks and required spikes

Ordered by how much they can hurt.

### 11.1 `setup-pyronaut` has no released `v1` — **blocker for CI**

`micronaut-projects/setup-pyronaut` `main` contains **only an initial empty commit**. The action
(`action.yml`, `scripts/`, `tests/`, a 14 KB README) exists only on the unmerged branch
`claude/pensive-brahmagupta-703mvz`. There are no tags, so `@v1` does not resolve.

Also from its README: Pyronaut's native launcher bundles come from GitHub releases of
`micronaut-projects/pyronaut`, and **while that repository is private the default `github.token`
is not sufficient** — a `PYRONAUT_RELEASE_TOKEN` secret with `contents: read` is required.

**Action:** merge and tag the action, or pin CI to the branch SHA in the interim; arrange the
release token. Track as a dependency of this project, not part of it.

### 11.2 Playwright Java on GraalPy — **highest technical unknown**

No precedent in Pyronaut, the petclinic, or any surveyed Micronaut repo. Unknowns:

- Does `Playwright.create()` work from GraalPy? It spawns a Node driver subprocess and talks to it
  over pipes — should be fine, but unproven.
- Playwright Java's API is heavily overloaded and uses nested `Options` builder classes and lambdas
  (`page.waitForNavigation(() -> ...)`). GraalPy → Java overload resolution and functional-interface
  conversion from Python callables both need checking.
- Playwright requires all calls on the thread that created the object. Interaction with GraalPy's
  context pooling and pytest execution threads is unknown.
- Driver/browser download size and caching in CI.
- `AriaRole`, `LoadState` and similar Java enums from Python.

**Spike (do this first, before any other work):** a standalone Pyronaut project with one pytest that
launches Chromium via Playwright Java, navigates to a data URL, and asserts on text. Time-box it.
**If it fails, the whole e2e requirement needs rethinking** — fallback options are Playwright Java
tests under `test-java/` as JUnit (loses the "one test session" story) or Selenium.

### 11.3 React 19 / Tailwind v4 / TanStack Router under GraalJS SSR — **high**

The petclinic's working configuration is React 18.2 with three hand-rolled polyfills. Every step of
the upstream frontend stack is newer than that. Unknowns: React 19's `react-dom/server.browser` API
surface on GraalJS; TanStack Router's SSR entry points; whether Radix components render server-side
cleanly. Mitigated by the staged approach in §8.1, but the plan should be honest that **the
delivered template may ship React 18**.

### 11.4 No per-test transaction support in the pytest integration — **medium**

Covered in §9.1. Affects test-suite design, not feasibility. Worth filing a Pyronaut issue.

### 11.5 `pyronaut` and Micronaut version pinning — **medium**

The petclinic pins `core.version = '5.2.0-SNAPSHOT'` and `micronaut-views-react:6.2.0`. A public
template cannot ship a SNAPSHOT. We need released versions of Pyronaut core, the Micronaut
Platform, and `micronaut-views-react` that are mutually compatible, plus a Pyronaut CLI release on
PyPI. **Confirm before starting.**

### 11.6 OpenAPI → TypeScript client fidelity — **medium**

Pyronaut generates OpenAPI from routes and dataclasses, which makes the generated-client story
possible. Not yet verified: whether `@Serdeable` dataclass schemas, `@Secured` security schemes, and
operation naming produce a spec that `@hey-api/openapi-ts` turns into an idiomatic SDK; and whether
there is a CLI command to *write* `openapi.json` to disk (upstream imports the app and dumps it —
we need an equivalent, possibly just fetching `/swagger/*.json` from a running dev server).

**Spike:** generate the spec from a two-endpoint Pyronaut app and run `openapi-ts` over it.

### 11.7 React email templates via `micronaut-email-template` — **low, high upside**

Whether `views-react` can serve as the rendering engine behind `TemplateBody`. If yes, we match
upstream's React Email with no Node at runtime. If no, fall back to Velocity/Thymeleaf and note the
gap. Cheap to check.

### 11.8 Smaller items

| Gap | Note |
| --- | --- |
| Password hashing library | §7.3 — needs a decision; avoid JNI for native-image |
| UUID PK representation on MySQL | §7.1 — `CHAR(36)` recommended, needs sign-off |
| Login endpoint shape | §7.4 — recommend adopting Micronaut's, not emulating OAuth2 form |
| `.env` support | §7.6 — Micronaut has no built-in `.env` loader; decide loader vs. documentation |
| Error response shape | §7.2 — must be fixed early; the generated TS client depends on it |
| Dev-only `/private` routes | `@Requires(env="dev")` — straightforward |
| CORS / `FRONTEND_HOST` | Largely moot under same-origin SSR; still needed if anyone splits the deployment |
| Sentry integration | Upstream has it; drop, or use Sentry's Java SDK. **Recommend dropping** and noting it |
| Adminer / Traefik | Dropped by design (Test Resources; single deployable). Document the rationale |
| Deployment docs | Upstream ships Compose + Traefik + Let's Encrypt guides. We need an equivalent for a container built by `pyronaut build --docker`. Non-trivial writing effort, easy to underestimate |
| Native image reflection config | The petclinic ships `reflect-config.json`/`resource-config.json`. Entities, DTOs, JDBC driver, Jakarta Mail and Playwright will all need attention if native is a supported target |
| Template mechanics | Upstream is a Copier template. Is this repo clone-and-rename, or a real template? §12 |
| Frontend tooling split | Upstream uses Bun + Biome + Vite; the petclinic uses npm + webpack. Pick one and be consistent |
| Dark mode, i18n, Storybook-ish polish | Upstream has appearance settings; parity requires porting them onto whatever CSS approach Stage A picks |

---

## 12. Open questions for review

1. **SSR-first or SPA-with-SSR-demo?** Full SSR is the interesting showcase but costs Vite HMR and
   forces cookie auth. Is that trade accepted?
2. **React 18 now, or hold for React 19?** Recommendation: ship 18, upgrade when the spike passes.
3. **Is this a Copier template, a `pyronaut create` feature set, or a clone-and-rename repo?**
   Upstream is Copier. This decision shapes the whole file layout.
4. **Password hashing:** accept `at.favre.lib:bcrypt` (native-image-safe) over Argon2 parity?
5. **Login endpoint:** adopt Micronaut Security's `/login` shape, or emulate FastAPI's OAuth2 form
   endpoint for drop-in client compatibility?
6. **Native image: supported target or demo?** Full support means maintaining reflection config for
   Playwright, Jakarta Mail and the JDBC driver.
7. **Which Pyronaut / Micronaut Platform versions are we allowed to pin?** (§11.5)
8. **Scope of deployment docs** — how much of upstream's Traefik/Let's Encrypt guidance do we
   replace versus simply drop?

---

## 13. Proposed sequence

| Phase | Work | Exit criteria |
| --- | --- | --- |
| **0. Spikes** | Playwright Java from pytest (§11.2); OpenAPI → `openapi-ts` (§11.6); `views-react` as email template engine (§11.7); confirm released versions (§11.5) | Each answered yes/no with a runnable proof |
| **1. Skeleton** | `pyproject.toml`, MySQL + Test Resources, Flyway V1, `User`/`Item` entities, repositories, health check, one pytest | `pyronaut test` green with a real MySQL container |
| **2. Auth** | Security JWT, `HttpRequestAuthenticationProvider`, roles, cookie mode, login/me endpoints, first-superuser bootstrap | Login and `@Secured` routes tested |
| **3. API parity** | All endpoints from §2.1, validation, error contract, pagination | Endpoint-for-endpoint parity, pytest per route |
| **4. Email** | Micronaut Email + Mailpit via Testcontainers, password recovery flow, `MailpitClient` assertions | Recovery flow tested end to end at the API level |
| **5. Frontend Stage A** | SSR + hydration for every screen on the petclinic's proven stack; generated TS client | Every route server-renders and hydrates |
| **6. E2E** | Playwright Java suite covering upstream's specs (login, signup, reset, items, user settings, admin) | Suite green locally |
| **7. CI** | `setup-pyronaut` workflow, caching, native build job | Green on a clean runner, twice (cache hit) |
| **8. Packaging & docs** | `pyronaut build --docker` / `--native --docker`, README with the comparison and benchmark, deployment guide | A reader can clone, run, deploy |
| **9. Stage B** | Tailwind v4 → shadcn → React 19 → TanStack Router, each gated on its spike | Shipped incrementally; none is a release blocker |

Phase 0 is not optional. Two of its four questions can invalidate a requirement.
