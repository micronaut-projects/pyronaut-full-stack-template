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
- **An annotation the processor cannot read from source is dropped silently**
  (pyronaut#173). The boundary was measured: a bare name for a scalar argument
  resolves (`Size(min=MIN_PASSWORD, ...)` keeps `minLength: 8`); a call
  expression does not (`QueryValue(defaultValue=str(SIZE))` loses the member,
  and the parameter is published `required: true`); and an annotation bound to
  a name does not (`PASSWORD = Size(min=8, max=128)` used as
  `Annotated[str, NotBlank, PASSWORD]` leaves the field with no length
  constraint at all). Write annotations out in full.
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
  compile but never reach the OpenAPI document (pyronaut#168). The cause is in
  `PythonAstParser`, which restores the `io.` prefix the run time strips only
  for `micronaut.` — so `io.swagger`, `io.vertx` and `io.netty` are all
  invisible to the compiler. Fixed in micronaut-core#13345 (draft, verified);
  until that ships, do not reach for these annotations. Docstrings *do*
  work — first sentence becomes `summary`, the whole docstring `description`.
  Note that the generated Java stubs carrying no annotations is normal and not
  the cause: annotation metadata lives in the bean definition rather than in
  the generated source, which is how `@Controller` and `@Secured` reach the
  runtime.
- **JUnit tests run against the system classloader** (pyronaut#169 — fixed
  upstream in PR #171, not yet in a release; `test-java/app/JUnitClassLoaderConfigurer.java`
  is the local stand-in and should go when 0.0.5 lands), so no
  project resource directory is reachable from them — not `views`, not
  `config`. Anything resolving `classpath:` breaks there while the identical
  pytest resolves fine. The server-render bundle is therefore resolved by file
  path in `tests-config/application-test.toml`; delete that override when the
  bug is fixed.
- **Stay on React 18.** React 19 renders correctly but takes over 300s where React 18 takes 0.20s
  for the same set of renders (micronaut-views#1198). Suspected cause is the unconditional
  `web-streams-polyfill` in `webpack.server.cjs`; the experiment is to make it conditional on
  `globalThis.ReadableStream` being absent and re-time. Not yet run.
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
| Docker | Test Resources starts MySQL; Testcontainers starts Mailpit; Playwright needs browsers. On Podman, Ryuk cannot bind-mount the machine's API socket (`operation not supported`), which fails only the Mailpit test — run with `TESTCONTAINERS_RYUK_DISABLED=true`. The `ryuk.disabled` property in `~/.testcontainers.properties` is **not** honoured by Testcontainers 2.x; only the environment variable works |
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
  Note that the renderer currently appends the hydration bootstrap to *every*
  render, after `</html>`, so a delivered email carries the whole view model in
  `rootProps` — the reset token included (micronaut-views#1199). Keep secrets
  out of an email's model until that is fixed; `tests/test_email.py` has a
  strict xfail that will start failing the moment it is.
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

## Agent skills

`.agents/skills/` holds three skills distilled from this port, following the conventions in
`micronaut-projects/micronaut-starter`:

- **pyronaut** — writing and debugging Pyronaut code, and the constructs that fail silently.
- **server-rendered-react** — adding screens without falling into the SSR/hydration trap below.
- **testing** — pytest, Playwright-from-Python, and services via Test Resources/Testcontainers.

They overlap this file deliberately: this file is the project's own context, the skills are
portable to any Pyronaut project. Keep them in step when a hard-won lesson is added here.

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

## Verifying an upstream fix against this template

A fix in `micronaut-core`'s `inject-python` cannot be verified by adding the jar
to this project: `pyronaut process` runs the processor from the **Pyronaut tool
runtime**, not from the project's build classpath. The tool runtime is
reconstructed from the installed wheel, which bundles the processor jars — so a
new core build has to travel through a rebuilt wheel.

```bash
# 1. micronaut-core, on the branch under test
./gradlew publishToMavenLocal -x test -x javadoc

# 2. pyronaut checkout — launchers once, wheel on every core change.
#    Pyronaut's projects declare their own repositories, so settings-level
#    mavenLocal() is ignored; pass an init script with
#    `gradle.allprojects { repositories { mavenLocal() } }`.
./gradlew -I /tmp/maven-local.init.gradle -Ppyronaut.micronaut.core.version=<version> assemble
./gradlew -I /tmp/maven-local.init.gradle -Ppyronaut.micronaut.core.version=<version> \
    :micronaut-pyronaut:installSdkWheel

# 3. ~/.pyronaut/settings.toml
[native-images]
base-url = "/path/to/pyronaut"
version = "0.0.4-SNAPSHOT"      # the projectVersion, not the wheel's .dev0

# 4. Between runs — the tool runtime is cached by descriptor hash, and
#    `pyronaut process` is cached by source hash.
rm -rf ~/.pyronaut/tools/<wheel-version> ~/.pyronaut/setup/<wheel-version>
rm -f __pyronaut__/processor-main.sha256 __pyronaut__/processor-test.sha256
```

Two traps. *Conflicting Pyronaut tool artifacts share filename …* means the jar
in m2 and the one bundled in the installed wheel differ — rebuild the wheel
after every `publishToMavenLocal`. And a locally built CLI resolves
`io.micronaut.pyronaut:*` for the **project** at the released version while the
tool runtime uses the checkout's, so `pyronaut test` can fail with a
`NoSuchMethodError` that has nothing to do with the change under test; reinstall
the released wheel when you are done.

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
