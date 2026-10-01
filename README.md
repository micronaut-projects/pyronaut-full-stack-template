# Pyronaut Full-Stack Template

A port of [`fastapi/full-stack-fastapi-template`](https://github.com/fastapi/full-stack-fastapi-template)
to [Pyronaut](https://github.com/micronaut-projects/pyronaut): the same application, written in the
same language, with fewer moving parts.

> **Status: working, incomplete.** The application runs, and `pyronaut test` is green: 38 tests
> across the API and a real browser, on Pyronaut 0.0.8 and Micronaut Views 6.3.1. The frontend is a
> deliberately plain React 19 stack — see
> [Current state](#current-state) for what is still missing. The full design and its open questions
> are in [PLAN.md](./PLAN.md).

- 🐍 **Python** application code on the Micronaut programming model, running on GraalPy.
- 🗄️ **[Micronaut Data JDBC](https://micronaut-projects.github.io/micronaut-data/latest/guide/)**
  with MySQL — SQL generated from method names at build time.
- 🧱 **Micronaut Validation** and **Micronaut Serialization** instead of Pydantic.
- 🔑 **Micronaut Security** — JWT in an HttpOnly cookie, so server rendering can read the user.
- ⚛️ **Server-rendered React** on GraalJS, in the same JVM. No Node in production.
- ✉️ **Micronaut Email** with React email templates rendered by the same GraalJS engine.
- 📬 **Mailpit** for local mail, started by Testcontainers in tests.
- 🧪 **pytest** through Micronaut's integration, plus **Playwright Java** for end-to-end tests.
- 🐋 **No Docker Compose.** Micronaut Test Resources starts MySQL on demand.

## What you no longer have to own

The point of this port is subtraction. Every row below exists in the upstream template and does not
exist here.

| Upstream needs | This template needs | Why |
| --- | --- | --- |
| `compose.yml`, `compose.override.yml`, `compose.deploy.yml` | *nothing* | Test Resources starts MySQL on demand; Testcontainers starts Mailpit for tests. Services are declared by dependency, not by YAML. |
| A Traefik reverse proxy and its TLS config | *nothing in development* | The API and the UI are the same origin on the same server. |
| A separate frontend container | *nothing* | The JVM serves the rendered HTML, the hydration bundle and the static assets. |
| An Adminer container | *nothing* | The Micronaut Control Panel covers datasource inspection. |
| Three Dockerfiles | `pyronaut build --jvm --docker` | The build tool writes the Dockerfile. |
| Five shell lifecycle scripts | `pyronaut test`, `pyronaut build` | Lifecycle is a CLI concern. |
| `alembic.ini`, `env.py`, `script.py.mako`, 5 revisions | `config/db/migration/V1__initial_schema.sql` | Flyway needs no runtime scaffolding. |
| A Python process **and** a Node process in development | **one JVM** | GraalPy and GraalJS run in the same VM. Node is a build-time bundler only. |
| N uvicorn workers to get past the GIL | one process, `micronaut.python.pool` | Several GraalPy contexts in one JVM, each with its own lock. |
| A running app import to produce `openapi.json` | a build artifact | OpenAPI is generated during `pyronaut process`. |
| React Email as a separate workspace compiled to Jinja | `frontend/emails/*.jsx` in the same bundle | Rendered by the GraalJS engine that renders the pages. |

## What this port actually bought

The claims below are things that changed during the port, not predictions. Where a claim is
inherited from the design rather than demonstrated, it says so.

### Fewer things to run, and fewer to get wrong

Upstream's local stack is five containers across three Compose files, plus a Vite dev server.
Here there is no Compose file at all: MySQL arrives because `micronaut-data-jdbc` and a Test
Resources module are declared, and Mailpit because a test asks for it. Services are a
**dependency**, not a YAML file someone has to keep in step with the code.

The same applies to lifecycle. Upstream has five shell scripts — `prestart.sh`, `test.sh`,
`tests-start.sh`, `format.sh`, `lint.sh` — and Alembic's `env.py`, `script.py.mako` and
`alembic.ini`. Here migrations are SQL files Flyway finds, seeding is a `StartupEvent` listener,
and the lifecycle is `pyronaut test` / `pyronaut build`.

### The whole test suite is one command, and it is real

```
$ pyronaut test
38 tests passed in 45.9s
```

31 API tests and 7 browser tests, in one run, against one embedded server, with a real MySQL and
a real Mailpit. Upstream runs Playwright separately against a Vite server with
`PLAYWRIGHT_BASE_URL` plumbing to connect the two.

The email tests are the clearest illustration: trigger a password reset, let Micronaut Email send
it, read the delivered message back out of Mailpit, extract the link from the rendered HTML, use
it, and confirm the old password stops working. Upstream does not assert on its email at all.

### OpenAPI is a build artifact, not a running-app artifact

Upstream obtains its OpenAPI document by importing and constructing the application:

```bash
uv run python -c "import app.main; import json; print(json.dumps(app.main.app.openapi()))"
```

That needs a working Python environment, a loadable app and valid configuration. Here
`pyronaut process` writes the document while compiling, from the route decorators and the
`@Serdeable` dataclasses. Generating the TypeScript client needs no server, no database and no
configuration — which is what makes the CI drift check in `.github/workflows/ci.yml` cheap enough
to run on every build.

Python docstrings become the documentation: first sentence to `summary`, the rest to
`description`.

### Mistakes surface at build time that would otherwise surface in production

`pyronaut process` fails on an unresolvable annotation, a bad generic or a repository method name
it cannot parse into SQL. `pyronaut validate-config` refused a change during this port because
removing a redirect left a required property unset — before anything started.

This is the compile-time DI argument made concrete, and it is the clearest structural difference
from the runtime-wiring model.

### One VM for Python and JavaScript

GraalPy and GraalJS run in the same JVM. The React pages and the transactional emails render
through the same engine, from the same bundle — so the email templates need no separate React
Email workspace and no build step producing Jinja. Node is a bundler, absent from production.

### Two languages, one container, no binding layer

Two of this application's beans are Java, in `src-java/`, and nothing about the Python that uses
them is special:

```python
from fullstack.security import PasswordHasher   # a Java class

@Singleton
class UserService:
    def __init__(self, users: UserRepository, passwords: PasswordHasher):
```

It goes the other way too. `CurrentUser` is Java and injects `UserService`, a Python class, taking
the Python entity back as a return value:

```java
public CurrentUser(UserService users) { this.users = users; }

public @Nullable User of(Authentication authentication) {
    return users.by_id(UUID.fromString(authentication.getName()));
}
```

Pyronaut generates a Java class for each Python type, so this is ordinary compilation: rename the
Python method and the Java stops compiling. One container, one configuration, one `pyronaut test`.

The two were moved to Java because every line of them was already calling a Java library or crossing
into one, and because a Java bean has no context affinity. A pooled Python type — every route module
is one — can hold a Java bean freely, where holding a Python singleton puts that type's work back
through the single interpreter context the singleton lives in. So this is the ordinary reason to
reach for Java here, and it is a narrow one: the rest of the application is Python because Python is
where the application logic reads best.

### It is faster than the original, and it was not at first

Every endpoint gained between the template's previous release and this one, and three of the four
gained a great deal. The work was not in this repository: benchmarking it found four upstream
performance bugs, and the fixes shipped in Pyronaut 0.0.7 and Micronaut Core 5.2.10.

| Endpoint | Before | Now | Change |
| --- | --- | --- | --- |
| `GET /api/v1/users/me` — JWT plus one indexed row | 2,856 req/s | **13,523** | **+374%** |
| `POST /api/v1/items` — write, in a transaction | 745 req/s | **3,730** | **+400%** |
| `GET /api/v1/items?page=0&size=20` — paged read | 1,267 req/s | **2,749** | **+117%** |
| `GET /api/v1/utils/health-check` — no database | 86,226 req/s | **89,387** | +3.7% |

Against the FastAPI template this is a port of, measured in the same run:

| Endpoint | FastAPI | This template | |
| --- | --- | --- | --- |
| `users-me` | 2,300 req/s | **13,523** | 5.9× |
| `items-create` | 1,240 req/s | **3,730** | 3.0× |
| `items-list` | 1,490 req/s | **2,749** | 1.8× |
| `health-check` | 28,756 req/s | **89,387** | 3.1× |

The two database-heavy endpoints are the ones worth noticing, because **before this work they were
slower than FastAPI** — `items-create` by 1.7× and `items-list` by 1.2×. Peak memory also crossed
over: **1,559 MiB against FastAPI's 2,372**, where this template previously used 2,268 MiB, because
the context pool default went from around 150 contexts to a handful.

Startup is still the weak spot and gained little: **10.8s to the first `200`, against FastAPI's
1.4s.** A JVM, a GraalPy context pool and a GraalJS engine all initialise before the first request.

#### What was actually wrong

None of it was the application code, and none of it was the GIL, which was the first guess:

- **A validated request body walked the whole classpath, twice per request.** Resolving a validation
  group missed the bean-introspection cache, and a miss re-ran discovery — every jar, every entry.
  That alone was 3.5× on the write path ([pyronaut#242](https://github.com/micronaut-projects/pyronaut/pull/242)).
- **A service with dependencies could not be per-context.** So every request funnelled into the one
  GraalPy context its singleton lived in, and adding contexts made it worse rather than better
  ([micronaut-core#13565](https://github.com/micronaut-projects/micronaut-core/pull/13565)).
- **The pool default was `processors * 2`**, the worst value of any measured
  ([#13557](https://github.com/micronaut-projects/micronaut-core/pull/13557),
  [#13578](https://github.com/micronaut-projects/micronaut-core/pull/13578)).
- **A list response built an entity per row to read one id.** The paged read now projects
  `ItemPublic` in the repository, so nothing per row crosses into Python.

#### How it was measured

Apple M2 Max, 12 cores, 64 GiB, macOS 26.5 (Darwin 25.5.0), arm64. One 12-core laptop, so treat the
ratios as meaningful and the absolute numbers as local.

32 concurrent clients via [k6](https://k6.io), 5,000 seeded rows, 30s warmup discarded, then the
median of three 60s runs — the ranges across those three were within 1% on every figure above. The
two applications run **one at a time**, never concurrently, so they never contend for CPU or for the
database. FastAPI runs with 4 uvicorn workers, its own Dockerfile's default.

**Both applications run against PostgreSQL**, which is the point of the comparison being fair: this
template ships MySQL, and the benchmark applies a Postgres overlay to a copy of it so that the two
are measured on the same database rather than MySQL being compared with Postgres. The harness, the
overlay and the fairness ledger are in `micronaut-projects/pyronaut-fastapi-benchmark`.

Login is excluded deliberately: FastAPI hashes with Argon2 and this template with BCrypt, so that
number measures a KDF choice rather than either framework.

### Honest limitations

- **Native image is deferred.** GraalJS is not supported inside a native image and server-side
  rendering needs it, so the first cut targets the JVM ([PLAN.md §4.4](./PLAN.md)). Everything
  else is kept native-friendly — no JNI dependencies — so the switch stays a build flag.
- **Hot reload works, including the browser.** `npm run watch` beside `pyronaut dev` and an edit to a
  React component is on screen without touching the browser. Micronaut Views React reloads the server
  bundle in process — it watches the file, drops its pool of GraalJS contexts, and the next render uses
  the rebuild — and `micronaut-views-react-dev`, a development-only dependency, tells the browser over
  server-sent events. Measured: new markup **within 10s with no restart**, against a 7.1s full restart
  before. `config/application-dev.toml` carries the configuration.

  Getting there took four upstream fixes, all now released:
  [pyronaut#183](https://github.com/micronaut-projects/pyronaut/pull/183) (dev mode no longer restarts
  for a watched directory) in Pyronaut 0.0.4;
  [pyronaut#190](https://github.com/micronaut-projects/pyronaut/issues/190) (the CLI adds
  `micronaut-runtime-osx` itself on macOS, without which the watcher polls and delivered nothing in two
  minutes) in 0.0.5; and
  [micronaut-views#1203](https://github.com/micronaut-projects/micronaut-views/pull/1203) and
  [#1204](https://github.com/micronaut-projects/micronaut-views/pull/1204) in Views 6.3.0. What is still
  missing is state-preserving HMR, which earns its complexity far less in an SSR app where the page's
  state comes from the server model on every navigation anyway
  ([micronaut-views#1197](https://github.com/micronaut-projects/micronaut-views/issues/1197)).
- **The frontend is React 19.** It renders on GraalJS in 20.4ms against React 18's 18.6ms — the same
  within noise. Two things had to land first, both in Views 6.3.0: the `MessageChannel` shim React 19's
  scheduler needs, which the module now installs itself
  ([micronaut-views#1201](https://github.com/micronaut-projects/micronaut-views/pull/1201)) — joined in
  6.3.1 by the `URL` and `URLSearchParams` globals React Router reaches for while server rendering
  ([#1208](https://github.com/micronaut-projects/micronaut-views/pull/1208)), so the project now carries
  no SSR polyfill of its own — and
  `hydrate-without-request`, without which React 19's extra `<link rel="preload" as="script">` landed in
  email bodies ([#1199](https://github.com/micronaut-projects/micronaut-views/issues/1199),
  [#1200](https://github.com/micronaut-projects/micronaut-views/pull/1200)). The earlier claim in this
  file that React 19 was three orders of magnitude slower was wrong, and so was blaming
  `web-streams-polyfill`; both are corrected on
  [#1198](https://github.com/micronaut-projects/micronaut-views/issues/1198).
- **Throughput and startup are unmeasured.** The concurrency argument — GraalPy context pooling
  instead of a worker fleet — is inherited from the design and has not been benchmarked here.
  Treat it as a claim to test, not a result.

### What the port cost upstream

A dozen bugs in the surrounding toolchain were found building this, which is itself worth weighing:
this is a younger stack than FastAPI's, and a port of this size surfaces rough edges. Almost all of
them are now fixed and released, and the template carries no workaround for any of them.

| Found | Fixed in |
| --- | --- |
| Swagger annotations never reached the OpenAPI document ([pyronaut#168](https://github.com/micronaut-projects/pyronaut/issues/168)) — the cause was in `PythonAstParser`, which restored the `io.` prefix only for `micronaut.` | Core 5.2.5 ([#13345](https://github.com/micronaut-projects/micronaut-core/pull/13345)) |
| A `Protocol` repository with a nullable `findById` generated an uncompilable interface ([#13346](https://github.com/micronaut-projects/micronaut-core/issues/13346)) | Core 5.2.5 ([#13358](https://github.com/micronaut-projects/micronaut-core/pull/13358)) |
| An id read off an entity was a Python `uuid.UUID`, so `findById` found nothing and `existsById` answered `False` for a row that was there ([#13382](https://github.com/micronaut-projects/micronaut-core/issues/13382)) | Core 5.2.7 ([#13385](https://github.com/micronaut-projects/micronaut-core/pull/13385)) |
| JUnit tests built their context against the system classloader, so no project resource directory was reachable ([pyronaut#169](https://github.com/micronaut-projects/pyronaut/issues/169)) | Pyronaut 0.0.5 ([#171](https://github.com/micronaut-projects/pyronaut/pull/171)) |
| The pytest integration accepted `transactional` and `rollback` and applied neither, because no `TestMethodInterceptor` ever ran ([pyronaut#174](https://github.com/micronaut-projects/pyronaut/issues/174)) | Pyronaut 0.0.4 ([#181](https://github.com/micronaut-projects/pyronaut/pull/181)) |
| POM-only coordinates could not be declared ([pyronaut#166](https://github.com/micronaut-projects/pyronaut/issues/166)) | Pyronaut 0.0.5 ([#170](https://github.com/micronaut-projects/pyronaut/pull/170)) |
| An email body carried the whole view model, reset token included, because the renderer always appended the hydration bootstrap ([micronaut-views#1199](https://github.com/micronaut-projects/micronaut-views/issues/1199)) | Views 6.3.0 ([#1200](https://github.com/micronaut-projects/micronaut-views/pull/1200)) |
| React 19 did not render at all on GraalJS: `ReferenceError: MessageChannel is not defined` ([#1198](https://github.com/micronaut-projects/micronaut-views/issues/1198)) | Views 6.3.0 ([#1201](https://github.com/micronaut-projects/micronaut-views/pull/1201)) |
| A `file:` server bundle killed the file watcher at startup, silently, so nothing reloaded ([#1203](https://github.com/micronaut-projects/micronaut-views/pull/1203)) | Views 6.3.0 |
| Nothing told the browser about a rebuild ([#1197](https://github.com/micronaut-projects/micronaut-views/issues/1197)) | Views 6.3.0 ([#1204](https://github.com/micronaut-projects/micronaut-views/pull/1204)) |
| `URL` and `URLSearchParams` were hand-rolled in every Pyronaut project doing React SSR, the petclinic included, because React Router needs them while server rendering and GraalJS has neither — without them every server-rendered route returned 500 | Views 6.3.1 ([#1208](https://github.com/micronaut-projects/micronaut-views/pull/1208)) |

| An annotation the processor could not read was dropped silently, taking its validation constraint with it — a dropped `Size` on a password field compiled, started and served ([pyronaut#173](https://github.com/micronaut-projects/pyronaut/issues/173)) | Core 5.2.9 ([#13366](https://github.com/micronaut-projects/micronaut-core/pull/13366)) — it now fails processing and names the fix |
| Nested Java annotations and enums were offered by the IDE stubs at module level under a name that could not be imported, and two of them could collapse onto one name ([pyronaut#222](https://github.com/micronaut-projects/pyronaut/issues/222)) | Pyronaut 0.0.6 ([#226](https://github.com/micronaut-projects/pyronaut/pull/226)) |
| The Test Resources server scope rejected the four-part POM-only coordinate, so the GraalJS dependency had to be spelled out as three concrete jars ([pyronaut#166](https://github.com/micronaut-projects/pyronaut/issues/166)) | Pyronaut 0.0.6 ([#215](https://github.com/micronaut-projects/pyronaut/pull/215)) |
| A route module lost pooling to any module-level decorator that was not a scope, so every mounted controller module was singleton-scoped | Core 5.2.9 ([#13488](https://github.com/micronaut-projects/micronaut-core/pull/13488)) |
| Validating a request body walked the whole classpath, twice per request, because resolving a validation group missed the introspection cache and a miss re-ran discovery. The write path served 769 req/s; with it cached, 2,721 | Pyronaut 0.0.7 ([#242](https://github.com/micronaut-projects/pyronaut/pull/242)) |
| A pooled type could not take constructor arguments, so a service with a dependency could not be per-context — and could not carry advice either, which would have made `@Transactional` on a pooled service silently do nothing. Pooling the services is worth 1.97× on a keyed read | Core 5.2.10 ([#13565](https://github.com/micronaut-projects/micronaut-core/pull/13565)) |
| `micronaut.python.pool.size` defaulted to `processors * 2`, the worst value measured, and this template had to set it by hand | Core 5.2.9 ([#13557](https://github.com/micronaut-projects/micronaut-core/pull/13557)) and 5.2.10 ([#13578](https://github.com/micronaut-projects/micronaut-core/pull/13578)) — now `processors / 2`, floored at 2 and capped at 8 |

Nothing on that list is still open, and the template carries no workaround for any of it. The one
outstanding external blocker is not a code fix: `setup-pyronaut` has no `v1` tag and its `main` is an
empty commit, which is what stops CI here.

## Requirements

- A JVM Pyronaut SDK and the `pyronaut` CLI
- GraalVM `25.4.4` and GraalPy `graalpy3.13-25.4.4` — the versions Pyronaut 0.0.8 is built against.
  A mismatch surfaces as `Unknown operation code 0` or a Truffle initialisation failure, not as a
  version error
- Node.js 22 and npm
- Docker, or another Testcontainers-compatible runtime, for MySQL and Mailpit in development and tests

## Getting started

```bash
cp .env.example .env     # then edit the values marked `changethis`
npm ci
npm run build            # writes views/ssr-components.mjs and static/client.js
pyronaut install
pyronaut dev
```

That is the whole local stack. `pyronaut dev` starts a MySQL container through Test Resources,
applies the Flyway migration, creates the first superuser and serves the application on
<http://localhost:8080>.

For local mail, run Mailpit and read it at <http://localhost:8025>:

```bash
docker run --rm -p 1025:1025 -p 8025:8025 axllent/mailpit
```

### Working on the frontend

```bash
npm run watch            # rebuilds both bundles on change
npm run check            # unit tests, production build, server-render smoke check
```

`npm run verify:ssr` renders every page and every email from the built server bundle and asserts the
emails carry no external stylesheet. It runs on Node rather than GraalJS, so it proves the bundle
shape and the render path, not GraalJS compatibility — but it is fast and it has already caught a
real bug.

### Running the tests

```bash
pyronaut test
```

One command runs the pytest API suite and the JUnit Playwright suite in the same session, against
the same embedded server, with MySQL and Mailpit supplied by containers.

`pyronaut test` needs a GraalPy virtual environment with pytest in it:

```bash
graalpy -m venv .venv
.venv/bin/python -m pip install --upgrade pip pytest
```

The browser suite is worth the setup. It has already caught four bugs that the API tests and `curl`
could not see, because in each case the server-rendered HTML was correct and the application was
broken underneath it — including static assets answering 401, so pages rendered perfectly and never
hydrated.

## Project layout

```
.agents/skills/ Agent skills: pyronaut, server-rendered-react, testing
src/            Python application sources
src-java/       Java sources, compiled into the same DI container
config/         application.toml and the Flyway migrations
frontend/       React pages, email templates and the SSR/hydration entry points
static/         CSS and the generated hydration bundle
views/          The generated server-render bundle
tests/          pytest API tests and the Playwright end-to-end suite
tests-config/   Test-only configuration
```

Generated bundles, `__pyronaut__/`, `.micronaut/` and `node_modules/` are not committed.

## Current state

| Area | State |
| --- | --- |
| API — users, items, login, recovery, utils | **Working.** 28 pytest tests against a real MySQL |
| Authentication | **Working.** JWT in an HttpOnly cookie, roles, first-superuser bootstrap |
| Server-rendered React and hydration | **Working.** 7 Playwright tests drive a real browser |
| React email templates | **Working.** Rendered on GraalJS, asserted through Mailpit |
| Compile-time OpenAPI and the TypeScript client | **Working.** `npm run generate-client` needs no running server |
| Frontend stack | React 19, webpack, react-router — deliberately the configuration proven to server-render on GraalJS. Tailwind, shadcn/ui and TanStack Router are [PLAN.md](./PLAN.md) Stage B |
| CI | Written, **never run** — no Actions minutes until 1 October, and `setup-pyronaut` has no `v1` tag yet |
| Native image | Deferred. GraalJS is not supported inside a native image and SSR needs it; see [PLAN.md §4.4](./PLAN.md) |

```
$ pyronaut test
38 tests passed in 45.9s
```

The `pyronaut` CLI is not on PyPI yet; it is published as a wheel on the
[Pyronaut releases page](https://github.com/micronaut-projects/pyronaut/releases).

Bugs found during this port and filed upstream are inventoried in
[What the port cost upstream](#what-the-port-cost-upstream), with the release each fix landed in.

## Deployment

The first cut targets the **JVM runtime**. GraalJS is not yet supported inside a GraalVM native
image, and server-side rendering needs GraalJS, so `pyronaut build --native` is a later phase rather
than an option today — see [PLAN.md §4.4](./PLAN.md). Every other choice in this template is
deliberately native-friendly, so that when GraalJS lands the change is a build flag.

```bash
pyronaut build --jvm --docker
```

## License

Apache License 2.0.
