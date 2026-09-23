# Pyronaut Full-Stack Template — Implementation Plan

A port of [`fastapi/full-stack-fastapi-template`](https://github.com/fastapi/full-stack-fastapi-template)
to [Pyronaut](https://github.com/micronaut-projects/pyronaut), built to showcase what the Micronaut
programming model gives a Python developer that FastAPI cannot.

**Status:** draft for review (revision 2). Nothing has been implemented yet.

---

## 1. Purpose and success criteria

This is not just a rewrite. The FastAPI template is the reference implementation of "a serious
Python web app"; the point of the port is that the same application, written in the same language,
comes out **smaller, faster, and with fewer moving parts** on Pyronaut.

Success criteria, in priority order:

1. **Feature parity.** Every user-visible feature of the FastAPI template works (§2).
2. **Fewer moving parts — the headline.** The FastAPI template's local stack is five containers
   wired by three Compose files (Traefik, Postgres, Adminer, backend, frontend) plus a Vite dev
   server. Ours is `pyronaut dev` and nothing else; Test Resources starts what it needs and stops
   it afterwards. **No Compose files exist in this repository.** §1.2 keeps score.
3. **One VM for Python and JavaScript.** GraalPy and GraalJS run in the same JVM. Development runs
   one process instead of two runtimes, and production ships no Node at all — Node is a build-time
   bundler dependency only.
4. **One deployable.** One artifact serves the API *and* server-renders the React app *and* renders
   the transactional emails. No separate frontend container, no reverse proxy needed to glue them.
5. **Compile-time OpenAPI.** The API description is a build artifact produced by
   `pyronaut process`, not something obtained by importing and starting the app (§8.2).
6. **A credible performance story.** A concurrency story that does not depend on running N worker
   processes (§4.3), and JVM throughput numbers against the same application on FastAPI. Native
   image startup and memory numbers are *not* part of the first cut — see §4.4.
7. **The showcase is legible.** A reader should be able to open one file and see why the Micronaut
   version is better, not have to take our word for it.
8. **Every gap found becomes an upstream fix.** This port is a forcing function for the wider
   Pyronaut/Micronaut stack. Bugs and missing features we hit go back to their home repositories as
   issues and pull requests, not into local workarounds (§12).

### 1.1 The advantages we are actually demonstrating

| Advantage | Where it shows up in this template |
| --- | --- |
| No GIL bottleneck | GraalPy context pooling gives true parallelism for Python request handling in one process — no gunicorn worker fleet. Verified: `pyronaut/src/main/docs/guide/concepts/threading/contextPool.adoc`. |
| Compile-time DI and validation | Beans, routes, repositories and constraints are resolved during `pyronaut process`, not at import time. Wiring mistakes are build failures. |
| Declarative data access | Micronaut Data JDBC generates SQL from method names at build time. No ORM session lifecycle, no lazy-loading surprises, no N+1 by accident. |
| No Pydantic problem | Pyronaut's own docs state Pydantic "does not work reliably in Pyronaut's multithreaded scenarios" (`usingPackagesJavaLibraries.adoc`). Micronaut Validation + Serde replace it with build-time-generated code. |
| The JVM ecosystem, one import away | MySQL JDBC, Flyway, Jakarta Mail, Playwright, Testcontainers, Spring Security Crypto — all `pip`-free imports. |
| Server-side React without Node in production | Micronaut Views React runs the SSR bundle on GraalJS inside the same JVM — for **pages and emails alike** (§7.5). Node is a build-time dependency only. |
| Real integration tests, no Compose | Test Resources starts MySQL; Testcontainers starts Mailpit. `pyronaut test` is the whole command. |
| Fast, honest packaging | `pyronaut build --jvm --docker` writes the Dockerfile and produces one image that serves API, SSR and email. Native image is deferred until GraalJS supports it (§4.4). |
| Compile-time OpenAPI | The API description falls out of `pyronaut process` as a build artifact — no app import, no running server, and contract breakage fails the build (§8.2). |
| One VM, two languages | GraalPy and GraalJS in the same JVM. Development runs one process; production ships no Node (§1.2). |
| Radical subtraction | No Compose files, no reverse proxy, no separate frontend container, no migration scaffolding, no shell lifecycle scripts (§1.2). |
| Drop to Java when it pays | `src-java/` compiles alongside Python in the same DI container (`projectStructure.adoc`). |

### 1.2 The simplification ledger

The headline claim is **subtraction**. The most persuasive thing this template can do is show a
reader what they no longer have to own. Every row below is a file, a process or a concept that
exists in the upstream template and does not exist in ours — and the README should present this
table before it presents any code.

| Upstream needs | We need | Why it goes away |
| --- | --- | --- |
| `compose.yml`, `compose.override.yml`, `compose.deploy.yml` | *nothing* | Test Resources starts MySQL on demand for `pyronaut dev` and `pyronaut test`; Testcontainers starts Mailpit for tests. Services are declared by *dependency*, not by YAML. |
| A Traefik reverse proxy container + its labels and TLS config | *nothing in development* | API and UI are the same origin on the same server. There is nothing to route between. |
| A separate frontend container running Vite/nginx | *nothing* | The JVM serves the SSR HTML, the hydration bundle and the static assets. |
| An Adminer container | *nothing* | The Micronaut Control Panel covers datasource inspection in development (as the petclinic already enables). |
| A Mailpit service pinned in Compose | a Testcontainers line in a test fixture | Started by the test that needs it, torn down after. |
| `backend/Dockerfile` + `frontend/Dockerfile` + `Dockerfile.playwright` | `pyronaut build --docker` | The build tool writes the Dockerfile. |
| `backend/scripts/prestart.sh`, `tests-start.sh`, `test.sh`, `format.sh`, `lint.sh` | `pyronaut test`, `pyronaut build` | Lifecycle is a CLI concern, not a shell-script concern. `prestart.sh` (migrate + seed) becomes Micronaut Flyway plus a `StartupEvent` listener. |
| `alembic.ini`, `app/alembic/env.py`, `script.py.mako`, 5 revision files | `config/db/migration/V1__*.sql` | Flyway needs no runtime scaffolding, no autogenerate machinery and no Python migration DSL. |
| A Python process **and** a Node process (Vite) in development | **one JVM** | GraalPy and GraalJS run in the same VM, in separate polyglot contexts. Node is a build-time dependency for bundling only, and absent from production entirely. |
| N uvicorn/gunicorn workers to get past the GIL | one process, `micronaut.python.pool` | Several GraalPy contexts inside one JVM, each with its own lock (§4.3). |
| A running app import to produce `openapi.json` | a build artifact | OpenAPI is generated during `pyronaut process` (§8.2). |
| `.python-version`, `uv.lock`, a virtualenv to activate | `pyproject.toml` | One manifest declares Python sources, Java dependencies, source layout, test engines and test resources. |
| React Email as a separate Bun workspace (`packages/react-email`) compiled to Jinja HTML | `frontend/emails/*.jsx` in the same bundle | The email templates are rendered by the same GraalJS engine that renders the pages (§7.5). |

Two numbers to publish once the port is real, because they are the whole argument:

- **Containers to run the app locally:** upstream 5, ours 0 (plus whatever Test Resources starts
  on demand and stops afterwards).
- **Language runtimes in production:** upstream 2 (CPython + Node, if SSR were added), ours 1.

The README's quick start should be exactly two commands — `npm ci && npm run build`, then
`pyronaut dev` — against upstream's Compose stack plus a Vite server plus a `uv sync`.

### 1.3 Where we improve on the API

"Port" does not mean "reproduce every wart". Where Micronaut lets us do better than the upstream
API without losing the shape of it, we should — and say so in the README, with the reasoning.
Candidates, each to be confirmed during Phase 3:

| Upstream | Ours | Why |
| --- | --- | --- |
| Token in `localStorage`, sent as a bearer header | JWT in an HttpOnly, SameSite cookie | Required for SSR (§4.2), and not reachable by XSS. A strict improvement. |
| `POST /login/access-token` taking an OAuth2 `x-www-form-urlencoded` form | JSON `POST /login` | The OAuth2 form is a FastAPI-ism inherited from its Swagger UI integration. The client is generated from OpenAPI, so nothing needs the form encoding. |
| `{"detail": "..."}` for errors, `{"detail": [...]}` for validation failures — two shapes under one key | One documented error shape, applied by a single exception handler | The generated TS client has to branch on the type of `detail` today. One shape is easier to consume and easier to document. |
| `skip`/`limit` query params, hand-rolled `count` query per endpoint | Micronaut Data `Pageable` + `Page`, still projected to `{data, count}` for client compatibility | Pagination becomes declarative; the count query is generated, not written. |
| `PUT /items/{id}` (full replace) next to `PATCH /users/{id}` (partial) | Consistent verbs across resources | Upstream's inconsistency is historical. |
| `POST /reset-password/` (trailing slash), `POST /utils/test-email/`, `GET /utils/health-check/` | No trailing slashes | Cosmetic, but a template teaches habits. |
| No email assertions in tests | `MailpitClient` assertions on subject, recipient and rendered HTML | §9.1. |
| OpenAPI produced at runtime by importing the app | OpenAPI produced at build time (§8.2) | Catches contract breakage during `pyronaut process`, not at deploy. |

Anything on this list that turns out to break the ported frontend in a way we cannot cheaply
absorb gets reverted to upstream's behaviour — parity wins ties.

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
- **Email:** templates authored as React Email components (`packages/react-email`), rendered to
  Jinja HTML, sent via SMTP, captured by Mailpit in dev.
- **Migrations:** Alembic, five revisions.
- **Tests:** pytest for the backend, Playwright (TypeScript) for the frontend.
- **CI:** GitHub Actions — backend tests, Playwright, docker-compose smoke test, pre-commit, coverage.
- **Local stack:** Docker Compose — Traefik, Postgres, Adminer, backend, frontend, Mailpit.
- **Deployment:** FastAPI Cloud, plus self-hosted Compose + Traefik with Let's Encrypt.

### 2.4 How upstream is consumed — resolved

Upstream is **not a Copier template** any more. There is no `copier.yml`; the surviving
`hooks/post_gen_project.py` is a vestigial line-ending fixer. The README says simply:

> Click the **Use this template** button at the top of this page to create a new repository.

Configuration then happens through the root `.env` file and the per-directory READMEs.

**Decision: follow suit.** This repository is a GitHub **template repository** — clone or "Use this
template", then configure. No Copier, no cookiecutter, no generator. Consequences:

- The repo must be *runnable as checked out*, with sensible `changethis` defaults and a boot-time
  refusal to run those defaults outside development (upstream does this; we keep it).
- Naming (`app`, the Micronaut application name, the Docker image name) is changed by the user, so
  it must be concentrated in as few places as possible — ideally `pyproject.toml` and
  `config/application.toml` only.
- We need the `.env` story to work (§7.6).

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
| pydantic-settings / `.env` | Micronaut `@ConfigurationProperties` + `application.toml` + env vars | To build (§7.6) |
| python-jose / PyJWT + OAuth2PasswordBearer | **Micronaut Security JWT** — `HttpRequestAuthenticationProvider`, `@Secured` | **Verified: `micronaut-security/test-suite-python/`** |
| pwdlib (argon2/bcrypt) | **Spring Security Crypto** — `BCryptPasswordEncoder` | **Decided (§7.3)** |
| `emails` + SMTP | **Micronaut Email** — `micronaut-email-javamail` + Angus Mail | Verified: module list |
| React Email templates | **`micronaut-email-template` rendered by `micronaut-views-react`** | Contract verified (§7.5) |
| Mailpit via Compose | Mailpit via Testcontainers + **`micronaut-email-mailpit-http-client`** for assertions | Verified: `micronaut-email/test-suite/.../OrderServiceTest.java` |
| Vite SPA in its own container | **Micronaut Views React** SSR + hydration, served by the app | Verified in petclinic |
| FastAPI `/openapi.json` | Pyronaut generates OpenAPI from routes and dataclasses, serves Swagger UI and ReDoc | Verified: `concepts/httpApis.adoc` |
| Playwright (TypeScript) | **Playwright Java + its JUnit 5 extension**, as Pyronaut JUnit 5 Python modules | Design settled, spike pending (§10.2) |
| Docker Compose for dev | **Test Resources** (MySQL) + Testcontainers (Mailpit) | Verified |
| Docker Compose + Traefik for deploy | `pyronaut build --jvm --docker` / `--native --docker` | Verified: `packaging.adoc` |
| `setup-python` + `uv` in CI | **`micronaut-projects/setup-pyronaut`** | Workflow prepared; cannot run before 1 Oct (§9) |

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
                │                                                      │
                │  Email: same GraalJS renderer, React components ─────┼──▶ SMTP
                └───────────┬──────────────────────┬──────────────────┘
                            │ JDBC                 │
                        ┌───▼────┐            ┌────▼────┐
                        │ MySQL  │            │ Mailpit │   ← dev/test only:
                        └────────┘            └─────────┘     started by Test
                                                              Resources /
                                                              Testcontainers
```

Python and JavaScript run in the same JVM in separate polyglot contexts — the petclinic proves this
combination works for pages; §7.5 extends it to emails.

### 4.2 The SSR decision, and what it costs

The upstream template is a **pure SPA**: Vite serves the frontend, the browser fetches an empty
shell, TanStack Router renders client-side, and auth state lives in `localStorage`.

We are going **SSR-first** (the explicit requirement, and the more interesting demo). Consequences
that must be designed for, not discovered:

1. **Auth must move to a cookie.** SSR runs on the server and cannot read `localStorage`. To
   server-render an authenticated page we need the token on the request. Micronaut Security
   supports `micronaut.security.authentication = cookie` with JWT in an HttpOnly cookie. This is
   strictly better security than the upstream's `localStorage` bearer token — worth calling out in
   the README — but it changes the login flow and the Playwright storage-state setup.
2. **No Vite dev server.** `pyronaut dev` serves everything; the JS watcher runs alongside
   (`npm run watch`, as in the petclinic). We lose Vite HMR and get webpack watch + browser reload.
   This is a real developer-experience regression versus upstream and should be acknowledged.
3. **Bundles.** `webpack.server.cjs` → `views/ssr-components.mjs` (pages **and** email components),
   `webpack.client.cjs` → `static/client.js`. Neither is committed.
4. **Route duplication.** Every SSR route needs a Python controller returning
   `ModelAndView("App", {...})` *and* a client route in the React tree. The petclinic shows the
   pattern; we should factor it so the two stay in sync.

### 4.3 Concurrency story

`micronaut.python.pool` is the headline. The FastAPI template scales by running multiple uvicorn
workers behind Traefik; we run one process with N GraalPy contexts and real parallelism. The
README should show this concretely (a CPU-bound endpoint under load, FastAPI vs. Pyronaut, same
machine).

### 4.4 Runtime and packaging: JVM first, native later

**Constraint:** GraalJS is not yet supported inside a GraalVM native image. Since server-side React
rendering is the whole point of the view layer, and it runs on GraalJS, **this template targets the
JVM runtime for its first cut.**

| Packaging format | First cut | Notes |
| --- | --- | --- |
| `wheel-jvm` (`pyronaut build --jvm`) | **Yes — default** | The development and distribution format. |
| `docker-jvm` (`pyronaut build --jvm --docker`) | **Yes — the deployable** | One image serving API, SSR and email. Pyronaut writes the Dockerfile. |
| Runnable fat JAR | Yes | Free; useful for anyone deploying without containers. |
| `wheel-native` / `docker-native` | **No** | Blocked on GraalJS in native image. |
| `wheel-crema` / `docker-crema` | **No, pending verification** | Crema is also a native production runtime, so it is presumed blocked for the same reason. Confirm separately rather than assuming — if Crema *can* host GraalJS, it becomes the first cut's fast-start option. |

Consequences to carry through the rest of the plan:

- **The performance story changes shape.** It is the concurrency story (§4.3) plus JVM throughput,
  measured against the same application on FastAPI — not millisecond cold starts. That is still a
  strong result and it is the honest one. Do not put native numbers in the README.
- **No native build job in CI** (§10), and no reflection-config maintenance burden in the first cut.
  That removes a real cost: entities, DTOs, the JDBC driver, Angus Mail and Spring Security Crypto
  would all have needed attention.
- **Native is planned work, not a dropped feature.** It has its own phase (§13, phase 11), gated on
  GraalJS support rather than on a date, and it is what the README should say: *native is coming,
  here is what it is waiting on.*
- **Design for native anyway, at zero cost.** Everything already chosen is native-friendly —
  compile-time DI, build-time serializers and validators, a pure-Java password encoder with no JNI
  (§7.3). The only thing standing between this template and a native build is GraalJS. Keep it that
  way: reject a dependency that would add a *second* native blocker, because the day GraalJS lands
  we want the switch to be one flag.
- **Say so in the README.** A template that quietly omits native invites the question; a template
  that states the constraint, names the blocker, and shows the work already done to be ready for it
  is more credible than one that claims a native build it cannot demonstrate.

**An option considered and not recommended:** an API-only build profile excluding `views-react`
*could* go native today, since the JSON controllers themselves have no GraalJS dependency. That
would demonstrate native startup — but it means maintaining a second profile, a second set of
reflection config, and a variant of the template with half its features. Not worth it for a
showcase. Revisit only if a native demo becomes a hard requirement before GraalJS support lands.

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
│       │   └── mail.py         MailService  (Micronaut Email + React templates)
│       ├── security/
│       │   ├── provider.py     HttpRequestAuthenticationProvider
│       │   ├── passwords.py    PasswordEncoder bean (Spring Security Crypto)
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
│       ├── dotenv.py           .env PropertySourceLoader (§7.6)
│       └── bootstrap.py        StartupEvent listener → first superuser
├── src-java/                   Java escape hatch (expected: empty or near-empty)
├── config/
│   ├── application.toml
│   ├── application-dev.toml
│   └── db/migration/           Flyway V1__… (MySQL)
├── frontend/
│   ├── client.jsx              hydrateRoot
│   ├── server.jsx              GraalJS polyfills + exports (App + email components)
│   ├── src/                    routes, components, generated API client
│   └── emails/                 React email components (§7.5)
├── static/                     css, images, generated client.js
├── views/                      generated ssr-components.mjs
├── tests/                      pytest — API + integration
│   ├── conftest.py             MicronautTest fixtures, MySQL, Mailpit
│   ├── test_login.py
│   ├── test_users.py
│   ├── test_items.py
│   ├── test_email.py           asserts via MailpitClient
│   └── e2e/                    JUnit 5 Python modules + Playwright Java (§8.2)
├── tests-config/
│   └── application-test.toml
├── test-java/                  Java test escape hatch
└── .github/workflows/ci.yml    setup-pyronaut (prepared; see §9)
```

---

## 6. `pyproject.toml` (proposed)

Versions below are **verified**. `core.version` and `platform.version` are taken from
`gradle.properties` in `micronaut-projects/pyronaut` itself — `pyronaut.micronaut.core.version=5.2.3`
and `pyronaut.micronaut.platform.version=5.1.0` — rather than from "latest on Maven Central", so the
template builds against the same versions the CLI does. (Maven Central has platform 5.1.5; pinning
ahead of the CLI is asking for trouble.) The rest are confirmed present on Maven Central.

```toml
[project]
name = "pyronaut-full-stack-template"
version = "0.1.0"

[tool.pyronaut.toolchain]
type = "jvm"

[tool.pyronaut]
repositories = ["mavenCentral"]
core.version = "5.2.3"          # latest release; NOT the petclinic's 5.2.0-SNAPSHOT
platform.version = "5.1.0"      # matches pyronaut's own gradle.properties

[tool.pyronaut.sources]
python = "src"
python-test = "tests"
java = "src-java"
java-test = "test-java"
resources = "config"
test-resources = "tests-config"
additional-resources = ["views", "static"]

[tool.pyronaut.test]
engine = "both"                 # pytest for API tests, JUnit for Playwright e2e (§8)

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
  "org.springframework.security:spring-security-crypto:7.1.1",
  "io.micronaut.email:micronaut-email-javamail",
  "io.micronaut.email:micronaut-email-template",
  "org.eclipse.angus:angus-mail",
  "io.micronaut.views:micronaut-views-react:6.2.0",
  "org.graalvm.polyglot:polyglot",
  "org.graalvm.polyglot:js",
  "io.micronaut.pyronaut:micronaut-pyronaut-logback",
]
build = [
  "io.micronaut:micronaut-context-python",
  "io.micronaut:micronaut-inject-python",
  "io.micronaut.data:micronaut-data-processor",
  "io.micronaut.serde:micronaut-serde-processor",
  "io.micronaut.validation:micronaut-validation-processor",
  "io.micronaut.security:micronaut-security-annotations",
]
test = [
  "io.micronaut.pyronaut:micronaut-pyronaut-pytest",
  "io.micronaut.pyronaut:micronaut-pyronaut-requests",
  "io.micronaut.test:micronaut-test-junit5",
  "io.micronaut.testresources:micronaut-test-resources-jdbc-mysql",
  "io.micronaut.email:micronaut-email-mailpit-http-client",
  "org.testcontainers:testcontainers",
  "com.microsoft.playwright:playwright",
  "com.microsoft.playwright:playwright-junit",
]
```

Modules managed by the platform BOM use versionless coordinates. `micronaut-views-react` is pinned
explicitly because the petclinic does so; drop the version if 6.2.0 is in the 5.1.5 platform BOM.

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
`Validator` bean by hand — we use declarative `@Valid` on `@Body` parameters and map
`ConstraintViolationException` to a single error shape with an exception handler. That gives us one
place to control the API error contract, which the generated TS client depends on.

### 7.3 Password hashing — **decided: Spring Security Crypto**

Per review, we use `org.springframework.security:spring-security-crypto`, following the official
Micronaut guide *Building a REST API — Spring Boot vs Micronaut: Security Basic Auth*
(`micronaut-guides/guides/building-a-rest-api-spring-boot-vs-micronaut-security-basic-auth`), which
uses exactly this pairing:

```java
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
...
passwordEncoder = new BCryptPasswordEncoder();
... passwordEncoder.matches(form.getSecret(), storedHash)
```

Why this is the right call, and better than the alternatives considered in revision 1:

- It is a **standalone artifact** — no Spring context, no Spring Boot, no auto-configuration. It is
  a crypto library that happens to live in the Spring group id.
- **Pure Java, no JNI.** That matters here: a JNI-backed Argon2 binding would undermine the
  `pyronaut build --native` story that is one of this template's headline features.
- It is a **Micronaut Launch feature** (`spring-security-crypto`), so `pyronaut create --features
  security,spring-security-crypto,...` produces the same dependency set. The template stays
  consistent with what the tooling generates.
- `DelegatingPasswordEncoder` gives us upstream's **rehash-on-login** behaviour (`pwdlib`'s
  `verify_and_update`) with an `{bcrypt}`-prefixed hash format and a documented upgrade path — so
  we match upstream's semantics, not just its strength.

Implementation: a Python `@Singleton` wrapping `PasswordEncoder`, injected into `UserService` and
the authentication provider. Argon2 remains available later via `Argon2PasswordEncoder` if
BouncyCastle is added; not in scope now.

### 7.4 Security

Verified against `micronaut-security/test-suite-python`, so this is low-risk:

- `HttpRequestAuthenticationProvider` subclassed in Python; `authenticate()` looks up the user by
  email, verifies via the `PasswordEncoder`, returns `AuthenticationResponse.success(id, roles,
  claims)`.
- Roles: `ROLE_USER`, `ROLE_SUPERUSER`. `@Secured(["ROLE_SUPERUSER"])` replaces upstream's
  `Depends(get_current_active_superuser)`.
- `Authentication` injected as a controller parameter replaces `CurrentUser`.
- Ownership checks (a user may read their own record; a user may only touch their own items) are
  not expressible as roles — they stay as explicit service-layer checks, same as upstream.
- **Login endpoint shape:** Micronaut Security's `/login` takes JSON `{"username","password"}`;
  upstream's `/api/v1/login/access-token` takes an OAuth2 form and returns
  `{"access_token","token_type"}`. **Recommendation: adopt the Micronaut shape** — the TS client is
  generated from OpenAPI anyway, so there is no reason to carry FastAPI's OAuth2 form quirk. Still
  open for review.
- **Cookie vs bearer:** see §4.2. Recommendation is `cookie` authentication mode so SSR works, with
  refresh-token support enabled.
- Password-reset tokens: a separate short-lived signed JWT with a `purpose: reset` claim, issued and
  validated by our own bean rather than reusing the access-token generator.

### 7.5 Email — React templates rendered on GraalJS

**This is a required feature of the plan, not an optional upside.** Upstream authors its emails as
React Email components and compiles them to Jinja HTML at build time. We render React components
*at send time, on the JVM, with no Node process* — the same GraalJS engine that renders the pages.

The contract checks out:

- `micronaut-email-template`'s `TemplateBodyDecorator` resolves a renderer via
  `viewsRendererLocator.resolveViewsRenderer(viewName, TEXT_HTML, data)` and renders a
  `TemplateBody` into the email body.
- `io.micronaut.views.react.ReactViewsRenderer` is declared
  `@Singleton class ReactViewsRenderer<PROPS> implements ViewsRenderer<PROPS, HttpRequest<?>>`.
- Its `render(String viewName, @Nullable PROPS props, @Nullable HttpRequest<?> request)` takes a
  **nullable request**, which is what the email path passes.

So `MailService` sends:

```python
Email.builder() \
    .to(recipient) \
    .subject(subject) \
    .body(TemplateBody(BodyType.HTML, ModelAndView("ResetPasswordEmail", props)))
```

Design points that need care:

1. **One SSR bundle, several roots.** `server-bundle-path` is a single setting, so
   `views/ssr-components.mjs` must export the page root (`App`) *and* each email component
   (`ResetPasswordEmail`, `NewAccountEmail`, `TestEmail`). `frontend/emails/` holds the latter.
2. **No hydration script in emails.** `ReactViewsRenderer` injects the client bundle URL for
   hydration. An email must not carry `<script src="/static/client.js">`. We need either a renderer
   configured without a client bundle for the email path, or to strip it. **If `views-react` offers
   no knob for this, that is an upstream contribution to `micronaut-views`** (§12) — a
   `client-bundle-url`-less render mode is generally useful for any non-hydrating render.
3. **Email CSS must be inline.** No external stylesheet, no Tailwind classes. The email components
   use inline `style` props — which is exactly what React Email does, so upstream's components port
   over closely.
4. **Renderer resolution by media type.** The locator asks for `text/html`. Confirm
   `ReactViewsRenderer` is selected for that media type and view name, and that it does not collide
   with another renderer on the classpath.

**Fallback if any of the above proves impossible:** Velocity or Thymeleaf templates via
`micronaut-views-*`. That is a parity regression versus upstream's React Email and should be treated
as a failure to be fixed upstream, not accepted.

Transport: `micronaut-email-javamail` + `org.eclipse.angus:angus-mail`, pointed at Mailpit in dev
and test via `javamail.properties.mail.smtp.host` / `.port`.

### 7.6 Configuration and `.env`

`@ConfigurationProperties("app")` Python class replacing `pydantic-settings`, plus `application.toml`
and environment variables. Upstream's "refuse to boot if `SECRET_KEY` is still `changethis`" check
maps to a `@PostConstruct` validation in the config bean — keep it.

Since we follow upstream's `.env`-driven model (§2.4), and Micronaut has **no built-in `.env`
loader**, we ship a small `PropertySourceLoader` in Python that reads `.env` from the project root
in the `dev` and `test` environments only. This is roughly thirty lines, doubles as a neat
demonstration of extending Micronaut from Python, and keeps the template's getting-started
instructions identical to upstream's. Production keeps using real environment variables.

### 7.7 Bootstrap

`ApplicationEventListener[StartupEvent]` in Python creates the first superuser from configuration,
replacing `initial_data.py` and the `prestart.sh` hook.

---

## 8. Frontend design

### 8.1 The hard part

The upstream frontend is React 19 + Vite 8 + Tailwind v4 + TanStack Router (file-based codegen) +
shadcn/Radix. The petclinic's proven SSR configuration is React **18.2** + webpack + hand-rolled
polyfills (`web-streams-polyfill`, `text-encoding`, and locally defined `URL`/`URLSearchParams`
because GraalJS does not provide them).

Porting the whole upstream stack onto GraalJS SSR in one step is the largest risk in this plan
(§10.3). The plan therefore stages it:

**Stage A — prove the stack.** Port the *screens* to the petclinic's proven SSR setup: React 18,
webpack, react-router. Plain CSS. Get every route server-rendering and hydrating, with the generated
API client, and the email components rendering through the same bundle. This is a working template.

**Stage B — modernise, one axis at a time,** each behind its own spike:
1. Tailwind v4 (build-time only — lowest risk).
2. shadcn/Radix components (SSR-safe in principle; `useLayoutEffect` warnings and portal behaviour
   need checking).
3. React 19 SSR on GraalJS (highest risk — new streaming internals, `react-dom/server.browser`
   surface).
4. TanStack Router with SSR (newer SSR story than react-router; file-based codegen adds a build step).

Stage A is the deliverable; Stage B items ship as they pass. **A template that ships with React 18
and works is worth more than one that targets React 19 and does not.**

### 8.2 Compile-time OpenAPI and the generated API client

This is one of the features the template exists to demonstrate, so it gets its own treatment in the
README rather than being buried in a build script.

**How FastAPI does it.** The OpenAPI document is built at runtime by walking the route table and
the Pydantic models. To get `openapi.json` out of the upstream template you must import and
construct the application:

```bash
# upstream scripts/generate-client.sh
uv run python -c "import app.main; import json; print(json.dumps(app.main.app.openapi()))" > openapi.json
```

That means client generation needs a working Python environment, a loadable app, and — because
importing `app.main` pulls in settings — a valid configuration. A contract mistake surfaces when
something runs.

**How we do it.** Pyronaut generates the OpenAPI description during `pyronaut process`, from the
route decorators and the `@Serdeable` dataclasses, as part of compiling the application
(`concepts/httpApis.adoc`). Concretely:

- The description is a **build output**, available without starting the app, without a database,
  and without valid runtime configuration.
- Schema generation is driven by the same build-time introspection that produces the serializers,
  so the document and the wire format cannot drift apart.
- A malformed route or an unserialisable type is a **build failure**, not a surprise in the
  generated client.
- Swagger UI at `/swagger-ui/index.html` and ReDoc at `/redoc/index.html` are served in development
  from that same artifact.

Pipeline:

```
pyronaut process  →  openapi.json (build artifact)  →  @hey-api/openapi-ts  →  frontend/src/client/
```

So `npm run generate-client` needs no running server and no app import — a genuinely better
developer loop than upstream's, and a good candidate for a CI check that fails when the committed
client drifts from the spec.

**Still to verify** (§11.5): that the generated spec is complete and accurate enough — schemas for
`@Serdeable` dataclasses, security schemes from `@Secured`, and operation ids/tags that produce
sensible method names — and exactly where `pyronaut process` writes the document, or whether we need
to add a command to emit it. If the document is currently only served and not written to disk,
**adding that is an upstream contribution** (§12), because every consumer of compile-time OpenAPI
will want it.

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

Email assertions use `MailpitClient` (`micronaut-email-mailpit-http-client`), asserting on subject,
recipients, and rendered HTML — better than upstream, which does not assert on email contents at
all. The React-rendered templates make this assertion genuinely valuable.

**Transactional isolation — to be fixed, not worked around.** Pyronaut's pytest integration states
that "`transactional`, `rollback` and `rebuild_context` are accepted for compatibility but have no
effect" (`testing/micronautTest.adoc`), and `Sql.Phase.AFTER_ALL` scripts do not run. Upstream's
suite leans on a transactional session fixture, and any serious Micronaut user will expect parity
with the Java `@MicronautTest`.

Per review, **closing this gap in Pyronaut is part of this project's scope** (§12). Plan:

1. Characterise the gap precisely against the Java behaviour (`micronaut-test`'s
   `TransactionalInterceptor`/`SpockInterceptor` equivalents): per-test transaction begin/rollback,
   `rebuild_context`, and `Sql` phases.
2. File an issue on `micronaut-projects/pyronaut` with a minimal reproducer drawn from this
   template's suite.
3. Implement it in `pyronaut-pytest` and send the PR.
4. Until it lands, the template uses an explicit truncate-between-tests fixture — clearly marked as
   a temporary measure with a link to the issue, so the workaround deletes itself later rather than
   becoming folklore.

### 9.2 End-to-end — Playwright Java via its JUnit 5 extension

Per review, this uses **Playwright Java's JUnit 5 integration**
([playwright.dev/java/docs/junit](https://playwright.dev/java/docs/junit)) rather than hand-rolled
fixtures, and rides Pyronaut's **JUnit 5 Python module** support — which is a much better fit than
pytest for this job, and removes most of the risk flagged in revision 1.

Playwright's extension (`com.microsoft.playwright:playwright-junit`) provides `@UsePlaywright`,
which manages the `Playwright`, `Browser`, `BrowserContext` and `Page` lifecycles and supports
per-class options (base URL, headless, tracing, storage state). Pyronaut's JUnit engine runs Python
modules as JUnit 5 tests with module-level `MicronautTest()`, module-level injected attributes, and
`@BeforeAll`/`@BeforeEach` lifecycle functions (`testing.adoc`).

Sketch:

```python
from com.microsoft.playwright.junit import UsePlaywright
from micronaut.test.extensions.junit5.annotation import MicronautTest
from org.junit.jupiter.api import Test

MicronautTest()
UsePlaywright(TestOptions)          # base URL, headless, storage state

embedded_server: Annotated[EmbeddedServer, Inject]

@Test
def test_login(page):
    page.navigate(f"{embedded_server.getURL()}/login")
    ...
```

This is genuinely novel — a Java browser-automation API, driven from Python, against a
server-rendered React app, in the same test session as the API tests, with the app under test being
the same embedded server. Upstream needs a separate Vite server and `PLAYWRIGHT_BASE_URL` plumbing;
we need neither.

Setting `[tool.pyronaut.test] engine = "both"` lets pytest own the API suite and JUnit own the e2e
suite in one `pyronaut test` run.

Remaining unknowns, now narrower (§10.2):
- Whether `@UsePlaywright`'s **parameter injection** of `Page` into a test function reaches Pyronaut's
  JUnit-Python test functions, and how it composes with `MicronautTest`'s own parameter resolver.
  If parameter injection does not compose, fall back to Playwright's non-extension API in
  `@BeforeEach`/`@AfterEach`, which needs no parameter resolution at all.
- GraalPy → Java conversion for Playwright's overloaded methods, nested `Options` builders, enums
  (`AriaRole`, `LoadState`) and lambda callbacks (`page.waitForNavigation(() -> ...)`).
- Playwright's single-thread affinity versus GraalPy context pooling in the test JVM.
- Driver/browser download and caching.

Auth setup: upstream's `auth.setup.ts` + `storageState` maps to `BrowserContext.storageState(...)`.
With cookie auth (§4.2) this is cleaner than upstream's localStorage dance.

Email-driven flows are testable end to end: trigger password recovery in the browser, read the
message via `MailpitClient`, extract the link, continue in the browser.

### 9.3 Frontend unit tests

Jest + Testing Library as in the petclinic, run by `npm test`. Kept separate from `pyronaut test`.

---

## 10. CI — prepared now, first run on or after 1 October

**Constraint from review:** this organisation has no GitHub Actions minutes until **1 October 2026**.
We therefore write and commit the workflow, review it by inspection, and validate it locally — but
do not expect a green run before then, and nothing in the delivery plan blocks on CI.

`.github/workflows/ci.yml`:

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
      - run: pyronaut test     # pytest API suite + JUnit Playwright suite
      - run: pyronaut build --jvm --docker
```

Notes:
- The bundle build **must** precede `pyronaut test` — SSR routes and email templates both fail
  without `views/ssr-components.mjs`.
- Add a Playwright browser cache step once §10.2 settles the cache path.
- **No native build job** — GraalJS is not supported in native image yet (§4.4). Add one when it is.
- No `docker compose` job — that is the point.
- **Local validation in the meantime:** run the same command sequence in a clean container, and use
  `act` or a scratch repository with minutes if one is available. Treat the workflow as unverified
  in the README until it has actually run.

Two dependencies on `setup-pyronaut` itself, tracked as upstream work (§12):

1. `micronaut-projects/setup-pyronaut` `main` is a **single empty commit**. The action
   (`action.yml`, `scripts/`, `tests/`, a 14 KB README) lives only on the unmerged branch
   `claude/pensive-brahmagupta-703mvz`, and there are no tags, so `@v1` does not resolve. Pin to a
   branch SHA in the interim.
2. Its README notes that Pyronaut's native launcher bundles come from GitHub releases of
   `micronaut-projects/pyronaut`, and **while that repository is private the default `github.token`
   is not sufficient** — a `PYRONAUT_RELEASE_TOKEN` secret with `contents: read` is required.

---

## 11. Remaining gaps, risks and spikes

Ordered by how much they can hurt. Items resolved since revision 1 are recorded in §11.7.

### 11.1 React 19 / Tailwind v4 / TanStack Router under GraalJS SSR — **high**

The petclinic's working configuration is React 18.2 with three hand-rolled polyfills. Every layer of
the upstream frontend stack is newer. Unknowns: React 19's `react-dom/server.browser` surface on
GraalJS; TanStack Router's SSR entry points; whether Radix renders server-side cleanly. Mitigated by
the staged approach in §8.1, but the plan should be honest that **the delivered template may ship
React 18**.

### 11.2 Playwright Java on GraalPy — **medium** (was high)

Narrowed considerably by the JUnit-extension approach (§9.2), which removes the need to hand-manage
Playwright's lifecycle from Python. What remains is listed in §9.2.

**Spike, still first in the queue:** a standalone Pyronaut project with one JUnit 5 Python module
that launches Chromium via `@UsePlaywright`, navigates to a data URL, and asserts on text. Time-box
it. Fallbacks in descending preference: Playwright's plain API in `@BeforeEach`; Playwright tests as
real Java under `test-java/`; Selenium.

### 11.3 No per-test transaction support in the pytest integration — **medium, and owned**

Now scoped as upstream work rather than a constraint (§9.1, §12).

### 11.4 Pyronaut CLI release availability — **medium**

**Confirmed by checking:** `core.version 5.2.3` and `platform.version 5.1.0` are what Pyronaut's own
`gradle.properties` pins, alongside GraalPy `graalpy3.13-25.3.4.1`. `micronaut-views-react 6.2.0` is
the current release.

**The CLI is not on PyPI.** `pip install pyronaut` fails with "No matching distribution found" — the
package does not exist there, despite the install instructions in the Pyronaut README. It is
published as a wheel on the [releases page](https://github.com/micronaut-projects/pyronaut/releases):
`v0.0.3` is the latest published (a prerelease) and `v0.0.4` is currently a draft. Until the PyPI
publish happens, `setup-pyronaut` must be pointed at a wheel URL rather than a version, and this
template's own instructions cannot say `pip install pyronaut`.

### 11.5 Compile-time OpenAPI fidelity and emission — **medium**

Pyronaut generates OpenAPI from routes and dataclasses, which makes the generated-client story
possible. Not yet verified: whether `@Serdeable` dataclass schemas, `@Secured` security schemes and
operation naming produce a spec that `@hey-api/openapi-ts` turns into an idiomatic SDK; and whether
there is a CLI command to *write* `openapi.json` to disk (upstream imports the app and dumps it — we
may need to fetch it from a running dev server instead).

**Spike:** generate the spec from a two-endpoint Pyronaut app and run `openapi-ts` over it.

### 11.6 React email rendering details — **low, but required**

The contract is verified (§7.5); what is unverified is the hydration-script suppression, renderer
selection by media type, and multi-root bundling. Cheap to check, and any shortfall is an upstream
contribution to `micronaut-views` rather than a blocker.

### 11.7 Smaller items

| Gap | Note |
| --- | --- |
| UUID PK representation on MySQL | §7.1 — `CHAR(36)` recommended, needs sign-off |
| Login endpoint shape | §7.4 — recommend adopting Micronaut's, not emulating OAuth2 form |
| Error response shape | §7.2 — must be fixed early; the generated TS client depends on it |
| `.env` loading | §7.6 — resolved by shipping a small Python `PropertySourceLoader` |
| Dev-only `/private` routes | `@Requires(env="dev")` — straightforward |
| CORS / `FRONTEND_HOST` | Largely moot under same-origin SSR; still needed if anyone splits the deployment |
| Sentry integration | Upstream has it; **recommend dropping** and noting it, rather than pulling in the Sentry Java SDK |
| Crema packaging | Presumed blocked with native, but unverified — worth a cheap check, since it would restore a fast-start story (§4.4) |
| FastAPI Cloud deployment | Upstream's primary deployment path has no analogue. Replace with the container story; do not pretend to match it |
| Adminer / Traefik | Dropped by design (Test Resources; single deployable). Document the rationale |
| Deployment docs | Upstream ships Compose + Traefik + Let's Encrypt guides. We need an equivalent for a container built by `pyronaut build --docker`. Non-trivial writing effort, easy to underestimate |
| Native image | Deferred: GraalJS is not supported in native image (§4.4). The petclinic ships `reflect-config.json`/`resource-config.json`; we skip that work for now, and keep every *other* choice native-ready so the eventual switch is one flag |
| Frontend tooling split | Upstream uses Bun + Biome + Vite; the petclinic uses npm + webpack. Pick one and be consistent — proposed: npm + webpack + Biome |
| Dark mode, appearance settings | Upstream has them; parity requires porting onto whatever CSS approach Stage A picks |

### 11.8 Resolved since revision 1

| Was | Now |
| --- | --- |
| Password hashing library undecided | **Spring Security Crypto** (§7.3) |
| React emails an unproven "opportunity" | **Required feature**, contract verified (§7.5) |
| `core.version` pinned to a SNAPSHOT | **5.2.3** release; platform 5.1.5 (§6) |
| Copier vs. clone-and-rename unknown | Upstream dropped Copier; **GitHub template repository** (§2.4) |
| Playwright approach unspecified | **Playwright JUnit 5 extension + Pyronaut JUnit Python modules** (§9.2) |
| Transactional pytest gap "worth filing" | **In scope as an upstream fix** (§9.1, §12) |
| `setup-pyronaut` blocking CI | CI prepared, deliberately unrun until 1 Oct (§10) |
| Native image an assumed deliverable | **Deferred** — GraalJS is not supported in native image; JVM runtime for the first cut (§4.4) |
| Can Python implement Java interfaces? | Yes — `micronaut-security/test-suite-python` proves it |

---

## 12. Upstream contributions

**Policy: a gap found here is a gap fixed there.** Where this port hits a bug or a missing feature in
the stack it builds on, the fix goes to the owning repository as an issue and, where we can, a pull
request. Local workarounds are permitted only as temporary measures, must be commented with a link
to the tracking issue, and are removed when the fix lands.

Known and likely targets:

| Repository | Item | Kind | Priority |
| --- | --- | --- | --- |
| `micronaut-projects/pyronaut` | pytest integration accepts `transactional`, `rollback` and `rebuild_context` and does not apply them — verified with a two-test probe. [#174](https://github.com/micronaut-projects/pyronaut/issues/174) | Issue filed | **High** |
| `micronaut-projects/setup-pyronaut` | Action exists only on an unmerged branch; `main` is empty; no `v1` tag (§10) | Merge + tag | **High — blocks CI** |
| `micronaut-projects/pyronaut` | The CLI is not on PyPI, but the README's install instructions say `pip install pyronaut` (§11.4) | Publish, or correct the docs | **High** |
| `micronaut-projects/pyronaut` | POM-only coordinates cannot be declared; every dependency is resolved as a jar. [#166](https://github.com/micronaut-projects/pyronaut/issues/166) | Issue filed | **High** |
| `micronaut-projects/micronaut-core` | Swagger annotations such as `@Tag` never reach the generated OpenAPI document, so a generated client cannot be grouped. Root cause: `PythonAstParser` restores the `io.` prefix the run time strips only for `micronaut.`, so every other `io.` library is invisible to the compiler. [pyronaut#168](https://github.com/micronaut-projects/pyronaut/issues/168) | Draft PR [micronaut-core#13345](https://github.com/micronaut-projects/micronaut-core/pull/13345) — **verified end to end** | Medium |
| `micronaut-projects/micronaut-core` | On `5.2.4-SNAPSHOT` a `Protocol` repository overriding `findById` with a nullable return generates an uncompilable interface; `X \| None` maps to a bare `X` rather than `Optional<X>`. Spelling it `Optional[X]` works. [micronaut-core#13346](https://github.com/micronaut-projects/micronaut-core/issues/13346) | Issue filed | **High — will break this template on 5.2.4** |
| `micronaut-projects/pyronaut` | JUnit tests use the system classloader, so no project resource directory is on their classpath and anything resolving `classpath:` fails there. [#169](https://github.com/micronaut-projects/pyronaut/issues/169) | **Fixed** — [PR #171](https://github.com/micronaut-projects/pyronaut/pull/171) merged 22 Sep 2026; drop `test-java/app/JUnitClassLoaderConfigurer.java` once a release carries it | **High** |
| `micronaut-projects/micronaut-test-resources` | The property resolver recurses until the stack overflows when asked for a key it does not own, for a bean built lazily during a request (§7.5) | Issue — reproducer outstanding | Medium |
| `micronaut-projects/pyronaut` | An annotation the processor cannot read from source is dropped silently: a call expression as an argument, or an annotation bound to a name. A dropped `Size` on a password field leaves no length constraint at all. [#173](https://github.com/micronaut-projects/pyronaut/issues/173) | Issue filed — warn rather than drop | **High** |
| `micronaut-projects/micronaut-views` | No way to render a React view without the hydration client-bundle script — needed for email bodies and any non-hydrating render (§7.5) | Issue + PR | Medium |
| `micronaut-projects/pyronaut` | GraalJS SSR polyfills (`URL`, `URLSearchParams`, TextEncoder/Decoder, web streams) are hand-rolled per project — the petclinic and this template will duplicate them | Issue: fold into `views-react` or document | Medium |
| `micronaut-projects/micronaut-views` | React 19 renders correctly but ~1500× slower than React 18 (0.20s vs >300s for the same renders). Suspected cause: the unconditional `web-streams-polyfill`. [#1198](https://github.com/micronaut-projects/micronaut-views/issues/1198) | Issue filed — experiment identified | **High** |
| `micronaut-projects/micronaut-views` | No hot module replacement in development; a rebuild and manual refresh per change. [#1197](https://github.com/micronaut-projects/micronaut-views/issues/1197) | Research issue filed | Medium |
| `micronaut-projects/pyronaut` | OpenAPI output fidelity for `@Serdeable` dataclasses and `@Secured` security schemes; a command to write `openapi.json` to disk (§11.5) | Issue | Medium |
| `micronaut-projects/pyronaut` | Whatever the Playwright spike turns up — Java overload resolution, functional-interface conversion from Python callables, enum handling (§11.2) | Issue(s) | Medium |
| GraalVM / `micronaut-views` | GraalJS support inside a native image — the one thing blocking a native build of this template (§4.4). Track it; re-test each GraalVM release | Track upstream | Medium |
| `micronaut-projects/pyronaut` | Whether Crema can host GraalJS, and if not, what it would take | Question | Low |
| `micronaut-projects/micronaut-email` | Mailpit is started by hand with a Testcontainers `GenericContainer`; a Test Resources provider would make this one line | Feature request | Low |
| `micronaut-projects/micronaut-data` | Anything found around UUID primary keys on MySQL (§7.1) | Issue | Low |
| `micronaut-projects/micronaut-guides` | A guide derived from this template, once it works | Contribution | Low |

Each phase in §13 should end with any issues it uncovered actually filed, rather than batched to the
end of the project.

---

## 13. Proposed sequence

| Phase | Work | Exit criteria |
| --- | --- | --- |
| **0. Spikes** | Playwright Java via JUnit extension from a Python module (§11.2); OpenAPI → `openapi-ts` (§11.5); React email render without hydration script (§11.6); confirm the compatible `pyronaut` CLI release (§11.4) | Each answered yes/no with a runnable proof; issues filed for every no |
| **1. Skeleton** | `pyproject.toml` at 5.2.3/5.1.5, MySQL + Test Resources, Flyway V1, `User`/`Item` entities, repositories, health check, `.env` loader, one pytest | `pyronaut test` green with a real MySQL container |
| **2. Auth** | Security JWT, `HttpRequestAuthenticationProvider`, Spring Security Crypto encoder, roles, cookie mode, login/me endpoints, first-superuser bootstrap | Login and `@Secured` routes tested |
| **3. API parity** | All endpoints from §2.1, declarative validation, error contract, pagination | Endpoint-for-endpoint parity, pytest per route |
| **4. Email** | Micronaut Email + Angus Mail, React email components through `views-react`, Mailpit via Testcontainers, password recovery flow, `MailpitClient` assertions | Recovery flow tested end to end at the API level, asserting rendered HTML |
| **5. Frontend Stage A** | SSR + hydration for every screen on the petclinic's proven stack; generated TS client; shared SSR bundle with the email roots | Every route server-renders and hydrates |
| **6. E2E** | Playwright Java suite covering upstream's specs (login, signup, reset, items, user settings, admin), `engine = "both"` | Suite green locally |
| **7. Upstream fixes** | Land the pytest transactional work and the other committed items in §12; remove the template's temporary workarounds | Workaround fixtures deleted; template runs on released upstream |
| **8. CI** | `setup-pyronaut` workflow committed and reviewed; first real run once minutes are available on 1 Oct; native build job | Green on a clean runner, twice (cache hit) |
| **9. Packaging & docs** | `pyronaut build --jvm --docker` (native deferred, §4.4), README leading with the simplification ledger (§1.2) and the measured numbers, the API-improvement rationale (§1.3), deployment guide, template-repository setup | A reader can use the template, run it, and deploy it |
| **10. Stage B** | Tailwind v4 → shadcn → React 19 → TanStack Router, each gated on its spike | Shipped incrementally; none is a release blocker |
| **11. Native** | Planned, not dropped (§4.4). Gated on GraalJS support in native image: re-test each GraalVM release, then add the reflection config, the `--native --docker` build and the CI job, and publish the startup and memory numbers | `pyronaut build --native --docker` produces a working image, and the README's performance section gains its cold-start figures |

Phase 0 is not optional. Two of its four questions can still change the shape of a requirement.
Phases 1–6 do not depend on CI and should proceed regardless of the October date. Phase 11 has no
date: it unblocks when GraalJS does, and the work in phases 1–9 is deliberately arranged so that
when it does, the change is a build flag and a reflection config — not a redesign.

---

## 14. Open questions for review

Reduced from revision 1; the rest have been settled above.

1. **SSR-first or SPA-with-SSR-demo?** Full SSR is the interesting showcase but costs Vite HMR and
   forces cookie auth. Is that trade accepted?
2. **React 18 now, or hold for React 19?** Recommendation: ship 18, upgrade when the spike passes.
3. **Login endpoint:** adopt Micronaut Security's `/login` shape, or emulate FastAPI's OAuth2 form
   endpoint for drop-in client compatibility?
4. **UUID primary keys:** `CHAR(36)` for readability, or `BINARY(16)` for efficiency?
5. **Is deferring native acceptable for the first cut?** GraalJS does not work in native image, and
   SSR needs GraalJS (§4.4). The recommendation is to ship JVM-only, say so plainly, and keep every
   other choice native-ready. The alternative — a second API-only profile that *can* go native — is
   not recommended.
6. **Scope of deployment docs** — upstream leads with FastAPI Cloud and falls back to Traefik +
   Let's Encrypt. How much do we replace versus simply drop?
