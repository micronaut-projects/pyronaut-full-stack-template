# Pyronaut Full-Stack Template

A port of [`fastapi/full-stack-fastapi-template`](https://github.com/fastapi/full-stack-fastapi-template)
to [Pyronaut](https://github.com/micronaut-projects/pyronaut): the same application, written in the
same language, with fewer moving parts.

> **Status: working, incomplete.** The application runs, and `pyronaut test` is green: 38 tests
> across the API and a real browser, on Pyronaut 0.0.6 and Micronaut Views 6.3.1. The frontend is a
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

Nothing on that list is still open, and the template carries no workaround for any of it. The one
outstanding external blocker is not a code fix: `setup-pyronaut` has no `v1` tag and its `main` is an
empty commit, which is what stops CI here.

## Requirements

- A JVM Pyronaut SDK and the `pyronaut` CLI
- GraalVM `25.4.4` and GraalPy `graalpy3.13-25.4.4` — the versions Pyronaut 0.0.6 is built against.
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
src-java/       Java sources, compiled into the same DI container (currently empty)
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
