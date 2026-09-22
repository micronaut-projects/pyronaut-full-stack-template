# Working on this repository

A port of `fastapi/full-stack-fastapi-template` to Pyronaut. The design, the open
questions and the gap list live in [PLAN.md](./PLAN.md) — read it before making
architectural decisions; most of them have already been made and justified there.

## The one thing to know

**The frontend is verified. The Python and JVM side has never been compiled.**

Everything under `src/` was written against verified reference sources (see
[Where the patterns come from](#where-the-patterns-come-from)) but no part of it
has been through `pyronaut process`. Expect real errors on the first run —
wrong import paths, annotation forms that do not resolve, Micronaut APIs that
differ from what was assumed. That is expected, not a surprise. Fix them; do not
assume the existing code is correct because it is committed.

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
