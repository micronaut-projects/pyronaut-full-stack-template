# Pyronaut Full-Stack Template

A port of [`fastapi/full-stack-fastapi-template`](https://github.com/fastapi/full-stack-fastapi-template)
to [Pyronaut](https://github.com/micronaut-projects/pyronaut): the same application, written in the
same language, with fewer moving parts.


- 🐍 **Python** application code on the Micronaut programming model, running on GraalPy.
- 🗄️ **[Micronaut Data JDBC](https://docs.micronaut.io/5.2.x/data/)**
  with MySQL — SQL generated from method names at build time.
- 🧱 **[Micronaut Validation](https://docs.micronaut.io/5.2.x/validation/)** and
  **[Micronaut Serialization](https://docs.micronaut.io/5.2.x/serde/)** instead of Pydantic.
- 🔑 **[Micronaut Security](https://docs.micronaut.io/5.2.x/security/)** — JWT in an HttpOnly
  cookie, so server rendering can read the user.
- ⚛️ **Server-rendered React** on GraalJS through **[Micronaut Views](https://docs.micronaut.io/5.2.x/views/)**,
  in the same JVM. No Node in production.
- ✉️ **[Micronaut Email](https://docs.micronaut.io/5.2.x/email/)** with React email templates
  rendered by the same GraalJS engine.
- 📬 **Mailpit** for local mail, started by Testcontainers in tests.
- 🧪 **pytest** through Micronaut's integration, plus **Playwright Java** for end-to-end tests.
- 🐋 **No Docker Compose.** [Micronaut Test Resources](https://docs.micronaut.io/5.2.x/test-resources/)
  starts MySQL on demand.

## What you no longer have to own

The upstream full stack template was a complex mishmash of scripts to orchestrate Docker and different VMs. This template simplfies all of that with Pyronaut feautures.

| Upstream needs | This template needs | Why |
| --- | --- | --- |
| `compose.yml`, `compose.override.yml`, `compose.deploy.yml` | *nothing* | Test Resources starts MySQL on demand; Testcontainers starts Mailpit for tests. Services are declared by dependency, not by YAML. |
| A Traefik reverse proxy and its TLS config | *not required* | The API and the UI are the same origin on the same server. |
| A separate frontend container | *nothing* | The JVM serves the rendered HTML, the hydration bundle and the static assets. |
| An Adminer container | *nothing* | The [Micronaut Control Panel](https://docs.micronaut.io/5.2.x/control-panel/) covers datasource inspection. Activate with `pyronaut dev --control-panel`. |
| Three Dockerfiles | `pyronaut build --jvm --docker` | The build tool writes the Dockerfile. |
| Five shell lifecycle scripts | `pyronaut test`, `pyronaut build` | Lifecycle is a CLI concern. |
| `alembic.ini`, `env.py`, `script.py.mako`, 5 revisions | `config/db/migration/V1__initial_schema.sql` | [Micronaut Flyway](https://docs.micronaut.io/5.2.x/flyway/) needs no runtime scaffolding. |
| A Python process **and** a Node process in development | **one JVM** | GraalPy and GraalJS run in the same VM. Node is a build-time bundler only. |
| N uvicorn workers to get past the GIL | one process, `micronaut.python.pool` | Several GraalPy contexts in one JVM, each with its own lock. |
| A running app import to produce `openapi.json` | a build artifact | [Micronaut OpenAPI](https://docs.micronaut.io/5.2.x/openapi/) generates the document during `pyronaut process`. |
| React Email as a separate workspace compiled to Jinja | `frontend/emails/*.jsx` in the same bundle | Rendered by the GraalJS engine that renders the pages. |

## Improvements to the original FastAPI template

### Fewer things to run, and fewer to get wrong

Upstream's local stack is five containers across three Compose files, plus a Vite dev server.
Here there is no Compose file at all: MySQL arrives because `micronaut-data-jdbc` and a Test
Resources module are declared, and Mailpit because a test asks for it. Services are a
**dependency**, not a YAML file someone has to keep in step with the code.

The same applies to lifecycle. Upstream has five shell scripts — `prestart.sh`, `test.sh`,
`tests-start.sh`, `format.sh`, `lint.sh` — and Alembic's `env.py`, `script.py.mako` and
`alembic.ini`. Here migrations are SQL files Flyway finds, seeding is a `StartupEvent` listener,
and the lifecycle is `pyronaut test` / `pyronaut build`.

### The whole test suite is one command

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

This works because of processing time DI which doesn't require runinning the application and a runtime-wiring model.

### One VM for Python and JavaScript

GraalPy and GraalJS run in the same JVM. The React pages and the transactional emails render
through the same engine, from the same bundle — so the email templates need no separate React
Email workspace and no build step producing Jinja. Node is a bundler, absent from production.

### Two languages, one container, no binding layer

Two of this application's components are written in Java, in `src-java/`, and Python code can invoke it with a simple import:

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

### It is faster than the original

Against the FastAPI template this is a port of, measured in the same run on the same hardware:

| Endpoint | FastAPI | This template | |
| --- | --- | --- | --- |
| `users-me` | 2,300 req/s | **13,523** | 5.9× |
| `items-create` | 1,240 req/s | **3,730** | 3.0× |
| `items-list` | 1,490 req/s | **2,749** | 1.8× |
| `health-check` | 28,756 req/s | **89,387** | 3.1× |


#### How it was measured

Apple M2 Max, 12 cores, 64 GiB, macOS 26.5 (Darwin 25.5.0), arm64. One 12-core laptop, so treat the
ratios as meaningful and the absolute numbers as local.

32 concurrent clients via [k6](https://k6.io), 5,000 seeded rows, 30s warmup discarded, then the
median of three 60s runs — the ranges across those three were within 1% on every figure above. The
two applications run **one at a time**, never concurrently, so they never contend for CPU or for the
database. FastAPI runs with 4 uvicorn workers, its own Dockerfile's default.

**Both applications run against PostgreSQL**, which is the point of the comparison being fair: this
template ships MySQL, and the benchmark applies a Postgres overlay to a copy of it so that the two
are measured on the same database rather than MySQL being compared with Postgres. 

### Honest limitations

- **Native image is deferred.** - Crema / Native execution needs more work for GraalJS, but it is coming.

## Requirements

- A JVM Pyronaut SDK and the `pyronaut` CLI
- GraalVM `25.4.4` and GraalPy `graalpy3.13-25.4.4` — the versions Pyronaut 0.0.8 is built against.
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
<http://localhost:8080>. Wait for:

```
Startup completed in 10833ms. Server Running: http://localhost:8080
```

The first start also pulls the MySQL image, so it takes longer than the ten seconds or so that
every start after it does.

`npm run build` is not optional. The bundles are gitignored, and both the pages and the emails are
rendered from `views/ssr-components.mjs`; without it every server-rendered route returns 500.

### Opening the home page

Open <http://localhost:8080/>. The home page is the dashboard and it needs a session, so signed out
you land on the login page instead.

Sign in as the superuser that was seeded during startup. That is `APP_FIRST_SUPERUSER` and
`APP_FIRST_SUPERUSER_PASSWORD` from your `.env` — `admin@example.com` / `changethis` if you have
not changed them yet. Signing in sets a JWT in an `HttpOnly` cookie and lands on the dashboard.

The login form is a plain form post. Micronaut Security answers it with a redirect: to the dashboard
when the credentials are right, back to the login page with an error when they are not.

Only a request that accepts `text/html` is redirected to the login page, so `/api/v1/**` still
answers an unauthenticated `fetch` with 401 rather than sending it to a login page it would read as
success.

| Page | |
| --- | --- |
| [`/`](http://localhost:8080/) | The dashboard. Signed in only |
| [`/items`](http://localhost:8080/items) | The item list, server-rendered with its first page already filled in |
| [`/settings`](http://localhost:8080/settings) | Account settings |
| [`/admin`](http://localhost:8080/admin) | User administration. Superusers only — a signed-in ordinary user is sent to a page saying so |
| [`/signup`](http://localhost:8080/signup) | Registration, for a user of your own |
| [`/recover-password`](http://localhost:8080/recover-password) | Sends a reset mail, which is where Mailpit below comes in |

Every one of those is rendered on the server by GraalJS and then hydrated, so view-source shows the
finished HTML rather than an empty root element.

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

The `pyronaut` CLI is not on PyPI yet; it is published as a wheel on the
[Pyronaut releases page](https://github.com/micronaut-projects/pyronaut/releases).


## Deployment

The first cut targets the **JVM runtime**. GraalJS is not yet supported inside a GraalVM native
image with crema, and server-side rendering needs GraalJS.

```bash
pyronaut build --jvm --docker
```

## License

Apache License 2.0.
