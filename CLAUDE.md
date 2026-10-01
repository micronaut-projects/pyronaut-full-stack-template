# Working on this repository

A port of `fastapi/full-stack-fastapi-template` to Pyronaut. The design, the open
questions and the gap list live in [PLAN.md](./PLAN.md) — read it before making
architectural decisions; most of them have already been made and justified there.

## State

The application runs and the suite is green: **38 tests, 0 failures, 0 skipped**
(31 API, 7 browser) on Pyronaut 0.0.8 (Core 5.2.11) and Micronaut Views 6.3.1. `pyronaut install`,
`process`, `dev` and `test` all pass against a real MySQL from Test Resources:
Flyway applies the schema, the first superuser is seeded, login issues a JWT cookie,
the React 19 pages server-render on GraalJS, emails render from the same bundle and
are asserted through Mailpit, and hot reload refreshes the browser.

Read a test count out of `__pyronaut__/reports/tests/junit.xml`, not off the exit
code — see the note in *Upstream work* about tasks that skip silently.

Benchmarked against the FastAPI original on 30 Sep 2026 — see the README, and the harness
in the adjacent `pyronaut-fastapi-benchmark` project. It leads on all four comparable
endpoints; it did not before, and closing that gap meant four upstream fixes rather than
changes here. Re-measure with that harness rather than trusting the numbers, and read the
fairness ledger first.

Still to do: the generated TypeScript client end to end, and CI.

## Gotchas this project already paid for

Each of these cost a debugging cycle. They are not in the Pyronaut docs.

- **No custom `__init__.py`.** Micronaut generates them for the GraalPy VFS and
  rejects your own. Packages are still packages — just do not write the file.
- **Generated `__init__.py` imports every module in its package, eagerly.** So
  two packages that import from each other deadlock at startup even when the
  individual modules would be fine. Keep cross-package dependencies
  one-directional: `security` and `controllers` may import `services`, never the
  reverse. A bean in `src-java/` sidesteps this entirely, which is one reason
  `PasswordHasher` is Java: `services` and `security` can both import it with no
  cycle to reason about.
- **`StartupEvent` and `ApplicationEventListener` live in
  `micronaut.context.event`**, not `micronaut.runtime.event`. When an import
  fails at runtime, grep `__pyronaut__/ide-stubs/` for the class name rather
  than guessing from the Java package.
- **An annotation the processor cannot read is now a compile error, not a silent
  drop.** Fixed in Core 5.2.9
  ([micronaut-core#13366](https://github.com/micronaut-projects/micronaut-core/pull/13366)),
  and re-measured on 0.0.6 — all three boundaries, since this used to be the worst
  trap in the project:
  - an annotation bound to a name (`PASSWORD = Size(min=8, max=128)` used as
    `Annotated[str, NotBlank, PASSWORD]`) fails processing with *"[PASSWORD] in
    Annotated[...] is a name bound to [Size(min=8, max=128)], not an annotation …
    Write the annotation inline."*
  - a call expression as an argument (`QueryValue(defaultValue=str(SIZE))`) fails
    with *"is not a compile-time constant … use a literal."*
  - a bare name for a scalar argument still **works**, and always did:
    `Size(min=MIN_PASSWORD, max=128)` keeps `minLength: 8` in the OpenAPI document.

  So the rule is no longer "write everything out in full or lose it silently". Both
  dangerous forms now stop the build and name the fix; a constant for a scalar
  argument is fine.
- **A Python exception cannot be an `ExceptionHandler` type parameter.** That
  bound is Java's `Throwable`. Catch Python exceptions in the controller.
- **A POM-only coordinate needs the four-part form**, `group:artifact:pom:version` — a
  three-part coordinate is resolved as a jar and fails
  ([pyronaut#170](https://github.com/micronaut-projects/pyronaut/pull/170)). It does not work
  everywhere yet: the test-resources-server scope still rejects four-part coordinates, so
  `pyproject.toml` keeps listing the three concrete jars GraalJS needs. Sent upstream as
  [pyronaut#215](https://github.com/micronaut-projects/pyronaut/pull/215); use the aggregator
  once that ships.
- **An id read from an entity is a Python `uuid.UUID`, and that is now fine.** It really is a
  Python object — `isinstance(id, uuid.UUID)` is `True`, not a foreign one that prints like one —
  but a repository accepts it: `findById` finds the row and `existsById` answers `True`. Before
  Core 5.2.7 neither did, silently, which is what the `UUID.fromString(str(value))` conversions in
  `services/` were for; they are gone.
  Fixed by [micronaut-core#13385](https://github.com/micronaut-projects/micronaut-core/pull/13385):
  a type variable erases to `Object`, and the interop layer was only converting when the target type
  was declared as `UUID`. `CrudRepository.findById(ID)` is exactly that shape. The same applied to
  `date`, `time`, `datetime`, `timedelta` and `timezone`, all covered by the fix.
  Annotate ids with Python's `uuid.UUID` rather than importing `java.util.UUID` — Pyronaut maps the
  two, so the generated Java is identical.
- **A Java name that collides with a Python keyword takes a trailing underscore.**
  `Pageable.from(page, size)` is written `Pageable.from_(page, size)`; no `getattr` needed.
  `app/paging.py` still wraps it, but only to clamp a page size arriving from a query parameter.
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
- **Swagger annotations used to be silently ignored** (pyronaut#168). The cause was in
  `PythonAstParser`, which restores the `io.` prefix the run time strips only
  for `micronaut.` — so `io.swagger`, `io.vertx` and `io.netty` were all
  invisible to the compiler. Fixed in Core 5.2.5
  ([micronaut-core#13345](https://github.com/micronaut-projects/micronaut-core/pull/13345)), so
  these annotations work now. Docstrings work too — first sentence becomes `summary`, the whole
  docstring `description`.
  Note that the generated Java stubs carrying no annotations is normal and not
  the cause: annotation metadata lives in the bean definition rather than in
  the generated source, which is how `@Controller` and `@Secured` reach the
  runtime.
- **The frontend is React 19, and every SSR polyfill it needs is upstream now** — so there is no
  `frontend/polyfills.js` any more, and do not reintroduce one without checking
  `host-polyfills.js` in the `micronaut-views-react` jar first. The module installs them there,
  evaluated before the server bundle: `MessageChannel` in 6.3.0, without which React 19's
  scheduler will not run ([#1201](https://github.com/micronaut-projects/micronaut-views/pull/1201)),
  and `URL`/`URLSearchParams` in 6.3.1, which React Router reaches for while server rendering
  ([#1208](https://github.com/micronaut-projects/micronaut-views/pull/1208)). GraalJS has none of
  the three, nor `setTimeout`. All of them are load-bearing rather than defensive: on 6.3.0, removing
  the hand-rolled `URL` pair returned 500 from every server-rendered route.
  Note that `npm run verify:ssr` cannot catch that class of regression — it runs on Node, which has
  these globals natively. The browser tests in `LoginFlowTest.py` are what actually exercise them.
  React 19 also needs `hydrate-without-request = false`, or its extra
  `<link rel="preload" as="script">` lands in email bodies
  ([#1199](https://github.com/micronaut-projects/micronaut-views/issues/1199)); `config/application.toml`
  sets it. React 19 renders in 20.4ms against React 18's 18.6ms — the "300s versus 0.20s" this file
  once claimed was wrong, as was blaming `web-streams-polyfill`.
- **`npm run build` before `pyronaut dev`.** The bundles are gitignored, so a
  fresh clone has none and every server-rendered route returns 500.
- **Killing `pyronaut dev` leaves stale Test Resources state.** The next start
  fails with "Test resource service is not available". Clear it with
  `rm -rf .micronaut/test-resources __pyronaut__/test-resources-session.json`.
- **`pkill -f "pyronaut dev"` does not stop the server.** The CLI spawns a
  separate JVM (`PyronautRunMain`) that keeps port 8080. The next `pyronaut dev`
  then dies with `BindException: Address already in use` — and if you are testing
  against `localhost:8080` you will be talking to the *old* process without
  noticing. Kill it by port: `lsof -ti :8080 | xargs kill -9`.

## Environment this needs

| Requirement | Why |
| --- | --- |
| GraalVM `25.4.4+1-graal` | Pyronaut's toolchain minimum is 25, but the Crema native build and GraalPy both want this exact build. Set `JAVA_HOME` to it — a stale Gradle daemon on another JDK fails the native build with `Could not find required field OptimizedDirectCallNode.callCount` |
| GraalPy `graalpy3.13-25.4.4` | Pinned in pyronaut's own `gradle.properties`. The version must match the GraalVM the project builds against and the one Pyronaut was built with — a mismatch shows up as `Unknown operation code 0` or an NPE creating the GraalPy context, not as a version error |
| The `pyronaut` CLI | **Not on PyPI.** `pip install pyronaut` fails. Install the wheel from https://github.com/micronaut-projects/pyronaut/releases (latest published: `v0.0.8`). Clearing `~/.pyronaut/setup/<version>` means re-running `pyronaut setup`; a dependency change does too |
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
- **Java for a bean that is all Java calls, Python for everything else.**
  `src-java/fullstack/security/` holds the two: `PasswordHasher`, every line of
  which calls Spring Security Crypto, and `CurrentUser`, which parses a JWT
  subject and asks a repository. Two reasons, and neither is "Java is faster" in
  general. A Python bean crossing into Java for its whole body pays an
  interpreter hop per call and adds nothing. And a Java bean has no context
  affinity, so a pooled type — every route module is one — can hold it, where
  holding a Python singleton drags that module's work back into the one context
  the singleton lives in.

  Python imports a Java bean the same way it imports any Java type
  (`from fullstack.security import PasswordHasher`), and Java injects a Python
  bean by its generated class (`app.services.UserService`, method `by_id`,
  returning `app.User`). Both directions are compiled, not reflective. Keep
  hand-written Java out of package `app`: that is where the generated stubs live,
  mirroring the Python package of the same name, so an import of a Java class
  there would be competing with a Python package — `fullstack` leaves no room for
  the question.

  Keep the Java side small. If a bean holds application logic, it belongs in
  Python even when it touches a Java library — `MailService` and the repositories
  are the line.
- **A list endpoint projects in the repository; a single-object one maps.**
  `ItemRepository.findAllProjected` and `findByOwnerIdProjected` return
  `Page[ItemPublic]` directly, so Micronaut Data builds the DTO from the row in
  Java and nothing per row crosses into Python. The entity path costs far more
  than it looks: it materialises an `Item` *and* an owner `User` per row, the
  latter only so the bean mapper can read `#{item.owner.id}` — a value that is
  already the `owner_id` column. Measured on a page of 20 at 32 concurrent
  clients: 2,199 req/s mapped, 3,157 projected.

  Two things to know before adding one. The fetch join is not optional on the
  entity path — remove it and `item.owner` is null, so the mapper throws on every
  request, which is a 100% failure rate rather than a subtle regression. And a
  projected DTO must carry **real types**: `ItemPublic.id` is `uuid.UUID` and
  `createdAt` is `Instant`, because as `str` they took whatever the JDBC driver's
  `toString` produced, which for a timestamp was local time with no zone
  (`2026-01-01 01:23:20` instead of `2026-01-01T00:23:20Z`). Serde renders the
  typed versions in the shapes the API already published, and both paths now agree.
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
workarounds. PLAN.md §12 has the tracked list, and the README has a table of what
each fix shipped in.

The template carries **no** workaround for an upstream bug and no polyfill of its own.
One item is open: `config/application.toml` names the two pooled-type dependencies this
application has decided about, which Core 5.2.11 understands
([micronaut-core#13587](https://github.com/micronaut-projects/micronaut-core/pull/13587))
but cannot yet be given — Pyronaut forwards a setting to the compiler only for an option a
registered annotation processor advertises, and the Python processor advertised none, so
the block is inert until [micronaut-core#13608](https://github.com/micronaut-projects/micronaut-core/pull/13608)
ships. `pyronaut process` still prints the eight warnings; passing
`JAVA_TOOL_OPTIONS=-Dmicronaut.python.pooled.ignoreDependencies=MailService,PasswordResetTokens`
silences them today. Everything else on the tracked list has shipped. Views 6.3.1 took
the URL polyfills ([#1208](https://github.com/micronaut-projects/micronaut-views/pull/1208)),
Pyronaut 0.0.6 took POM-only coordinates in the test-resources-server scope
([#215](https://github.com/micronaut-projects/pyronaut/pull/215)) and the nested
annotation stubs ([#226](https://github.com/micronaut-projects/pyronaut/pull/226)), and
Core 5.2.9 took both the unreadable-annotation report
([#13366](https://github.com/micronaut-projects/micronaut-core/pull/13366)) and module
route pooling ([#13488](https://github.com/micronaut-projects/micronaut-core/pull/13488)).

The performance work landed in 0.0.7: a validated request body no longer walks the
classpath twice per request ([pyronaut#242](https://github.com/micronaut-projects/pyronaut/pull/242)),
a pooled type may take constructor arguments and carry advice
([micronaut-core#13565](https://github.com/micronaut-projects/micronaut-core/pull/13565)),
and the pool default is `processors / 2` rather than a number this template had to set by
hand ([#13557](https://github.com/micronaut-projects/micronaut-core/pull/13557),
[#13578](https://github.com/micronaut-projects/micronaut-core/pull/13578)). All three were
found by benchmarking this application; see `micronaut-projects/pyronaut-fastapi-benchmark`.

`setup-pyronaut` still has no `v1` tag and its `main` is an empty commit, which is a
maintainer action rather than something that can be sent as a PR. It blocks CI here.

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
