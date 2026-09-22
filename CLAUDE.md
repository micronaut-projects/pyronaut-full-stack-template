# Working on this repository

A port of `fastapi/full-stack-fastapi-template` to Pyronaut. The design, the open
questions and the gap list live in [PLAN.md](./PLAN.md) — read it before making
architectural decisions; most of them have already been made and justified there.

## State

The backend compiles and runs. `pyronaut install`, `pyronaut process` and
`pyronaut dev` all pass against a real MySQL from Test Resources: Flyway applies
the schema, the first superuser is seeded, login issues a JWT cookie, and the
React pages server-render on GraalJS with the hydration bundle injected.

Still to do: confirm the pytest suite passes, the Playwright end-to-end suite,
the generated TypeScript client, and CI.

## Gotchas this project already paid for

Each of these cost a debugging cycle. They are not in the Pyronaut docs.

- **No custom `__init__.py`.** Micronaut generates them for the GraalPy VFS and
  rejects your own. Packages are still packages — just do not write the file.
- **Generated `__init__.py` imports every module in its package, eagerly.** So
  two packages that import from each other deadlock at startup even when the
  individual modules would be fine. Keep cross-package dependencies
  one-directional: `security` and `controllers` may import `services`, never the
  reverse. `app/passwords.py` sits at the top level for exactly this reason.
- **`StartupEvent` and `ApplicationEventListener` live in
  `micronaut.context.event`**, not `micronaut.runtime.event`. When an import
  fails at runtime, grep `__pyronaut__/ide-stubs/` for the class name rather
  than guessing from the Java package.
- **Annotation values must be compile-time constants.** `QueryValue(defaultValue=str(SIZE))`
  is silently dropped — the processor reads source, it does not evaluate. The
  parameter then shows up as `required: true` in the OpenAPI schema.
- **A Python exception cannot be an `ExceptionHandler` type parameter.** That
  bound is Java's `Throwable`. Catch Python exceptions in the controller.
- **POM-only Maven coordinates cannot be declared.** Pyronaut resolves every
  dependency as a jar. Declare the concrete jars instead — see the GraalJS
  comment in `pyproject.toml`, and pyronaut#166.
- **`Pageable.from(...)` is unreachable** — `from` is a Python keyword. Use the
  `page_request()` helper in `app/paging.py`.
- **The JWT secret must be at least 256 bits** for HS256. A short one fails only
  at login, as "Cannot obtain an access token".
- **Do not let Test Resources resolve a property it does not own.** Its resolver
  re-enters itself and the stack overflows, and it only bites beans built lazily
  during a request. This is what `app/mail_session.py` works around; read that
  module before touching mail configuration.
- **Operation ids must be unique across the whole API.** A collision is not an
  error: Micronaut OpenAPI appends a number, and the generated client grows a
  `signup1` whose digit depends on declaration order. This is why the page
  handlers in `controllers/views.py` are named `*_page`.
- **Swagger annotations are silently ignored.** `@Tag` and friends import and
  compile but never reach the OpenAPI document (pyronaut#168). Docstrings *do*
  work — first sentence becomes `summary`, the whole docstring `description`.
  Note that the generated Java stubs carrying no annotations is normal and not
  the cause: annotation metadata lives in the bean definition rather than in
  the generated source, which is how `@Controller` and `@Secured` reach the
  runtime.
- **`additional-resources` does not reach the test classpath** (pyronaut#169).
  The server-render bundle is therefore resolved by file path in
  `tests-config/application-test.toml`. Delete that override when the bug is
  fixed — it exists for no other reason.
- **`npm run build` before `pyronaut dev`.** The bundles are gitignored, so a
  fresh clone has none and every server-rendered route returns 500.
- **Killing `pyronaut dev` leaves stale Test Resources state.** The next start
  fails with "Test resource service is not available". Clear it with
  `rm -rf .micronaut/test-resources __pyronaut__/test-resources-session.json`.

## Environment this needs

| Requirement | Why |
| --- | --- |
| GraalVM 25+ | Pyronaut's toolchain minimum |
| GraalPy `graalpy3.13-25.3.4.1` | Pinned in pyronaut's own `gradle.properties` |
| The `pyronaut` CLI | **Not on PyPI.** `pip install pyronaut` fails. Install the wheel from https://github.com/micronaut-projects/pyronaut/releases (latest published: `v0.0.3`) |
| Docker | Test Resources starts MySQL; Testcontainers starts Mailpit; Playwright needs browsers |
| Node.js 22 + npm | Bundling only — not needed at runtime |

The cloud session this repository was scaffolded in had none of the first four,
which is why the backend is unverified.

## Commands

```bash
npm run check         # unit tests + both bundles + server-render smoke check
npm run build         # required before `pyronaut dev` or `pyronaut test` —
                      # SSR routes and email templates both need views/ssr-components.mjs
npm run watch         # rebuild bundles on change, alongside `pyronaut dev`

pyronaut install      # resolve Java dependencies
pyronaut process      # compile Python + Java sources; also generates OpenAPI
pyronaut dev          # run, with MySQL from Test Resources
pyronaut test         # pytest API suite + JUnit Playwright suite
```

`npm run verify:ssr` renders every page and every email from the built bundle.
It runs on Node, so it proves the bundle shape and the render path, not GraalJS
compatibility — but it is fast, and it already caught the navigation links being
mounted outside the router context. Keep it green, and add a case to
`frontend/ssr-smoke.mjs` whenever a new render root is added.

## Conventions

- **Python naming.** Entity and DTO attributes use `camelCase`, because they map
  directly to Micronaut Data columns and JSON fields. Service and module-level
  functions use `snake_case`. This split is deliberate — do not "fix" it.
- **Decorators over imperative calls.** Use declarative `@Valid` on `@Body`
  parameters rather than injecting a `Validator` and calling it, so the error
  contract stays in one exception handler. (The petclinic does the imperative
  version; we are not copying that.)
- **One error shape.** Every failure returns `ApiError` — `{message, errors}`.
  The upstream template returns two different shapes under `detail`; see
  PLAN.md §1.3.
- **No Docker Compose.** Services come from Test Resources or Testcontainers.
  If you are reaching for a compose file, the answer is somewhere else.
- **Emails are React components** in the same SSR bundle as the pages, rendered
  on GraalJS. They must use inline styles only — no stylesheet link, no classes.
- **JVM runtime, not native.** GraalJS does not work in a native image yet
  (PLAN.md §4.4). Keep every other choice native-friendly: no JNI dependencies,
  so that when GraalJS lands the change is a build flag.

## The SSR trap

The server sends the model for **one** screen. Treating that model as if it
described the whole application is the mistake this codebase has already made
four times, in four places:

- the route table dispatched on the server's `page` prop, so every client-side
  navigation re-rendered whichever screen the server sent first;
- three of the four screens only rendered from `initial` and had no fetch to
  fall back on;
- the navigation chrome took the signed-in user from `data.user`, so it vanished
  as soon as you navigated away from the screen that supplied it;
- the session lookup ran once on mount, while signed out, and never again.

Every one of them left the server-rendered first paint completely correct, so
nothing but a real browser doing a real navigation could see them. When adding
a screen: give it a fetch path for when `initial` is null, take session state
from `App` rather than the page model, and add a case to `LoginFlowTest.py`
that navigates to it *from another page* rather than loading it directly.

Signing in is a full `window.location.assign('/')`, not a client-side
navigation. Identity changes belong to the server in an SSR-first app;
reconstructing the authenticated shell on the client is what caused three of
the four bugs above.

## Where the patterns come from

When unsure how something is expressed in Pyronaut, check these before guessing:

| Question | Verified source |
| --- | --- |
| Entities, repositories, controllers, SSR views | `micronaut-projects/pyronaut-petclinic`, branch `codex/react-rest-spa` |
| Implementing a Java interface from Python, `@Secured`, auth providers | `micronaut-projects/micronaut-security`, module `test-suite-python` |
| Mailpit via Testcontainers, `MailpitClient` assertions | `micronaut-projects/micronaut-email`, `test-suite/.../OrderServiceTest.java` |
| pytest fixtures, bean lookup, `@ConfigurationProperties` | `micronaut-projects/pyronaut`, `functional-test/app` and `src/main/docs/guide` |
| Pinned versions | `micronaut-projects/pyronaut`, `gradle.properties` |

## Upstream work

Gaps found here go back to their home repositories as **draft PRs**, not local
workarounds. PLAN.md §12 has the tracked list. Two are committed:

1. **`pyronaut-pytest` ignores `transactional` / `rollback` / `rebuild_context`.**
   Until fixed, tests use an explicit truncate-between-tests fixture — mark it
   temporary with a link to the issue so it deletes itself later.
2. **`setup-pyronaut` has no `v1` tag** and its `main` is an empty commit; the
   action lives on an unmerged branch.

## Next steps

1. Get `pyronaut install && pyronaut process` to pass. This is the real
   unblocking step and it will surface most of the latent errors in `src/`.
2. Confirm `pyronaut process` writes an OpenAPI document, and run
   `npm run generate-client` over it (PLAN.md §11.5).
3. Write the controllers (`src/app/controllers/`) — the API surface is
   inventoried in PLAN.md §2.1.
4. Write the pytest suite, then the Playwright JUnit suite.

Phase 0 spikes in PLAN.md §13 were never run; the environment could not support
them. Playwright-from-Python (§11.2) is still unproven and is the largest
remaining unknown after the frontend stack.
