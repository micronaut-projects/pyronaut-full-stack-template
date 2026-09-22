---
name: testing
description: Write and run tests for a Pyronaut application — pytest against the API, Playwright Java in a real browser, and services supplied by Test Resources and Testcontainers. Use when users add tests, ask why a test cannot see a service, or need a browser test for server-rendered pages.
license: Apache-2.0
compatibility: Pyronaut projects using micronaut-pyronaut-pytest, micronaut-test-junit5 and a container runtime
metadata:
  author: micronaut-projects/pyronaut-full-stack-template
  version: "1.0.0"
---

# Testing

`pyronaut test` runs pytest and JUnit in one invocation, against one embedded server, with real services started on demand. There is no Docker Compose file to bring up first.

## Goal

Tests that exercise the real thing — a real database, real mail, a real browser — without the ceremony usually required to arrange them, and that fail with a message naming the cause.

## Trigger Examples

Should trigger:

- "Add a test for this endpoint."
- "Add a browser test for this page."
- "The test cannot find the database / the mail server."
- "`pyronaut test` reports that the engine failed to execute tests."

Should not trigger:

- Frontend unit tests in isolation (`npm test`).
- Questions about what to test rather than how.

## Prerequisites

`pyronaut test` runs pytest on the embedded GraalPy runtime, which cannot take packages from a CPython environment:

```bash
graalpy -m venv .venv
.venv/bin/python -m pip install --upgrade pip pytest
```

Missing this produces `TestEngine with ID 'pyronaut-pytest' failed to execute tests`, with instructions in the error.

## Procedure

1. Choose the engine the test belongs to.
2. Let the services come to the test.
3. Do not depend on data another test can change.
4. Make the assertion explain the failure.

### 1) Choose the engine the test belongs to

`[tool.pyronaut.test] engine = "both"` runs both in one pass.

**pytest** for API and service tests — ordinary `test_*.py` with fixtures:

```python
@pytest.fixture
def application_context(request):
    fixture = micronaut_test_fixture(request, MicronautTest(environments=["test"]))
    yield fixture
    fixture.stop()

@pytest.fixture
def client(application_context):
    return requests.with_context(application_context)
```

**JUnit 5 as a Python module** for anything needing class-level lifecycle — a browser, for instance. `MicronautTest()` at module level hands the file to the JUnit engine and excludes it from pytest discovery. Name it `*Test.py`.

```python
MicronautTest()
TestInstance(TestInstance.Lifecycle.PER_CLASS)

embedded_server: Annotated[EmbeddedServer, Inject]

@BeforeAll
def start_browser(): ...
```

`@BeforeAll`/`@AfterAll` are instance methods here, so `PER_CLASS` is mandatory — without it JUnit refuses to discover the class at all.

### 2) Let the services come to the test

Anything with a Micronaut Test Resources module — databases especially — needs only the dependency and `[tool.pyronaut.test-resources] additional-modules`. The container starts on demand and the connection properties are injected.

Anything without one is started from the test with Testcontainers, driven from Python against the Java API:

```python
@pytest.fixture(scope="session")
def mailpit():
    container = (GenericContainer(DockerImageName.parse("axllent/mailpit"))
                 .withExposedPorts(1025, 8025)
                 .waitingFor(Wait.forHttp("/").forPort(8025)))
    container.start()
    try:
        yield {"app.smtp-port": str(container.getMappedPort(1025)), ...}
    finally:
        container.stop()
```

Feed the mapped ports into `MicronautTest(properties=...)`. Session scope, so the container starts once.

Reaching for a Compose file means something has gone wrong.

### 3) Do not depend on data another test can change

The pytest integration does **not** implement per-test transactions: `transactional`, `rollback` and `rebuild_context` are accepted and have no effect. With a shared Test Resources server the database also outlives the run.

So: generate unique values rather than relying on a clean table, and assert on shape rather than on specific data another test might mutate.

```python
# Fragile: the API suite renames this user
assert "Administrator" in heading

# Robust
assert heading.startswith("Hi, ")
```

### 4) Make the assertion explain the failure

A bare `assert response.status() == 200` on a browser test tells you nothing, and the server-side exception is in the test report rather than the console. Put the evidence in the message:

```python
assert response.status() == 200, (
    f"GET /login returned {response.status()}: {str(page.content())[:600]}"
)
```

This turns a debugging session into a single run. Server-side stack traces are captured into `__pyronaut__/reports/tests/junit.xml` and attributed to the failing test, so they are recoverable after the fact without re-running.

## Browser tests

Playwright Java works from GraalPy. Use its plain API rather than the `@UsePlaywright` JUnit extension, which delivers `Page` by parameter injection where Pyronaut's JUnit-Python modules take injections at module level.

The application under test is the same embedded server the API tests use — no separate frontend server, no base-URL plumbing. Take the URL from the injected `EmbeddedServer`.

Playwright downloads every browser on first use, around 400 MB. Cache `~/.cache/ms-playwright` in CI.

## Verification

```bash
npm run check    # frontend: unit tests, bundles, render checks
pyronaut test    # everything else, in one run
```

The bundles must be built before `pyronaut test`, or every server-rendered route returns 500.
