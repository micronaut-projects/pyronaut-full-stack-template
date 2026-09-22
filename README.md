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

Three bugs found during this port are filed upstream:
[#166](https://github.com/micronaut-projects/pyronaut/issues/166) (POM-only dependencies cannot be
declared), [#168](https://github.com/micronaut-projects/pyronaut/issues/168) (Swagger annotations do
not reach the OpenAPI document) and
[#169](https://github.com/micronaut-projects/pyronaut/issues/169) (`additional-resources` is missing
from the test classpath).

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
