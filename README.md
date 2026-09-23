# Pyronaut Full-Stack Template

A port of [`fastapi/full-stack-fastapi-template`](https://github.com/fastapi/full-stack-fastapi-template)
to [Pyronaut](https://github.com/micronaut-projects/pyronaut): the same application, written in the
same language, with fewer moving parts.

> **Status: working, incomplete.** The application runs, and `pyronaut test` is green: 35 tests
> across the API and a real browser. The frontend is a deliberately plain React 18 stack — see
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
35 tests passed in 1m 17s
```

28 API tests and 7 browser tests, in one run, against one embedded server, with a real MySQL and
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
- **No Vite HMR.** Server rendering means `pyronaut dev` plus a webpack watcher: a rebuild and a
  manual refresh on every change, losing component state, against Vite's sub-100ms in-place module
  swap. Raised as [micronaut-views#1197](https://github.com/micronaut-projects/micronaut-views/issues/1197).
- **The frontend is React 18, not 19** — but not for the reason this file used to give. React 19 is
  not slow on GraalJS; without a shim it does not render at all, returning a 500 with
  `ReferenceError: MessageChannel is not defined`. React 19's scheduler requires `MessageChannel`
  where React 18 fell back to a timer, and GraalJS has neither. With the shim in
  `frontend/polyfills.js` React 19 renders in 20.4ms against React 18's 18.6ms — the same, within
  noise. Measured and corrected on
  [micronaut-views#1198](https://github.com/micronaut-projects/micronaut-views/issues/1198); the earlier "three orders of magnitude slower" claim was
  wrong, as was the `web-streams-polyfill` theory.

  What still holds React 19 back here is [micronaut-views#1199](https://github.com/micronaut-projects/micronaut-views/issues/1199): React 19 also puts
  `<link rel="preload" as="script">` in `<head>`, so an email body gains a second piece of hydration
  apparatus it cannot use. Once [micronaut-views#1200](https://github.com/micronaut-projects/micronaut-views/pull/1200) lands, the upgrade is a
  version bump. The rest of the modern stack is staged in [PLAN.md](./PLAN.md).
- **Throughput and startup are unmeasured.** The concurrency argument — GraalPy context pooling
  instead of a worker fleet — is inherited from the design and has not been benchmarked here.
  Treat it as a claim to test, not a result.

Four bugs in the surrounding toolchain were found during the port, three of them now with a fix
in flight ([pyronaut#166](https://github.com/micronaut-projects/pyronaut/issues/166) — merged,
[pyronaut#168](https://github.com/micronaut-projects/pyronaut/issues/168),
[pyronaut#169](https://github.com/micronaut-projects/pyronaut/issues/169),
[micronaut-core#13346](https://github.com/micronaut-projects/micronaut-core/issues/13346)), which is
itself worth weighing: this is a younger stack than FastAPI's, and a port of this size surfaces rough
edges.

## Requirements

- A JVM Pyronaut SDK and the `pyronaut` CLI
- GraalVM 25 or later, and GraalPy
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
| Frontend stack | React 18, webpack, react-router — deliberately the configuration proven to server-render on GraalJS. Tailwind, shadcn/ui, React 19 and TanStack Router are [PLAN.md](./PLAN.md) Stage B |
| CI | Written, **never run** — no Actions minutes until 1 October, and `setup-pyronaut` has no `v1` tag yet |
| Native image | Deferred. GraalJS is not supported inside a native image and SSR needs it; see [PLAN.md §4.4](./PLAN.md) |

```
$ pyronaut test
35 tests passed in 1m 17s
```

The `pyronaut` CLI is not on PyPI yet; it is published as a wheel on the
[Pyronaut releases page](https://github.com/micronaut-projects/pyronaut/releases).

Bugs found during this port and filed upstream:
[pyronaut#166](https://github.com/micronaut-projects/pyronaut/issues/166) (POM-only dependencies
cannot be declared — fixed, [PR #170](https://github.com/micronaut-projects/pyronaut/pull/170)),
[pyronaut#168](https://github.com/micronaut-projects/pyronaut/issues/168) (Swagger annotations do not
reach the OpenAPI document — fix in
[micronaut-core#13345](https://github.com/micronaut-projects/micronaut-core/pull/13345)),
[pyronaut#169](https://github.com/micronaut-projects/pyronaut/issues/169) (JUnit tests build their
context against the system classloader — fixed,
[PR #171](https://github.com/micronaut-projects/pyronaut/pull/171)),
[pyronaut#173](https://github.com/micronaut-projects/pyronaut/issues/173) (an annotation the processor
cannot read from source is dropped silently, validation constraints included) and
[micronaut-core#13346](https://github.com/micronaut-projects/micronaut-core/issues/13346) (a nullable
`findById` override stops compiling on 5.2.4).

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
