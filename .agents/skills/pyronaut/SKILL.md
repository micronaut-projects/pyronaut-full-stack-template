---
name: pyronaut
description: Write and debug Pyronaut application code — Python on the Micronaut programming model. Use when users add controllers, entities, repositories, services or configuration to a Pyronaut project, when `pyronaut process` fails, or when an annotation or import that looks correct has no effect at runtime.
license: Apache-2.0
compatibility: Pyronaut projects using the JVM toolchain, GraalVM 25+ and GraalPy
metadata:
  author: micronaut-projects/pyronaut-full-stack-template
  version: "1.0.0"
---

# Pyronaut

Python source, compiled at build time into Micronaut bean definitions. Most of it reads like ordinary Python, and the places where that intuition breaks are where the time goes.

## Goal

Produce Pyronaut code that compiles under `pyronaut process` and behaves the same at runtime as it reads on the page — with particular attention to the constructs that fail **silently** rather than loudly.

## Trigger Examples

Should trigger:

- "Add a controller / entity / repository to this Pyronaut project."
- "`pyronaut process` fails with a type or annotation error."
- "This validation constraint isn't being applied."
- "This import works in the IDE but fails at runtime."

Should not trigger:

- "Explain what Micronaut is."
- Pure Java Micronaut work with no Python sources.

## Procedure

1. Check the generated stubs before guessing an import.
2. Write annotations with literal arguments only.
3. Keep cross-package imports one-directional.
4. Compile, then run — the two fail differently.

### 1) Check the generated stubs before guessing an import

`__pyronaut__/ide-stubs/` is generated from the actual classpath and is the authoritative answer to "where does this class live". Grep it rather than inferring from the Java package:

```bash
grep -rn "class StartupEvent" __pyronaut__/ide-stubs/
```

Java packages map by dropping a leading `io.`: `io.micronaut.http` → `micronaut.http`, `io.swagger.v3...` → `swagger.v3...`. But the mapping does not tell you which *module* a class ended up in. `StartupEvent` and `ApplicationEventListener` are in `micronaut.context.event`, not `micronaut.runtime.event`, and only the stubs say so.

A wrong import compiles and fails at context startup with `ModuleNotFoundError`, usually reported against whichever bean was being constructed rather than the module with the bad import.

### 2) Write annotations with literal arguments only

**This is the highest-value rule in this skill.** The processor reads annotation arguments from source; it does not evaluate them. A non-literal argument is discarded without a warning.

```python
# WRONG — the constraint silently disappears, and the API accepts anything
PASSWORD = Size(min=8, max=128)
password: Annotated[str, NotBlank, PASSWORD]

# WRONG — the default is dropped, and the parameter is published as required
size: Annotated[int, QueryValue(defaultValue=str(DEFAULT_SIZE))] = DEFAULT_SIZE

# RIGHT — repetitive, and correct
password: Annotated[str, NotBlank, Size(min=8, max=128, message="...")]
size: Annotated[int, QueryValue(defaultValue="100")] = DEFAULT_SIZE
```

Failures here are invisible: the code reads correctly, compiles, starts, and serves. A dropped `Size` on a password field is a security bug that only a test will find. Write every constraint out in full, and add a test that asserts the constraint rejects bad input.

### 3) Keep cross-package imports one-directional

Micronaut generates a package `__init__.py` that eagerly imports **every** module in the package. Two packages that import from each other therefore deadlock at context startup, even when the individual modules would be fine.

Establish a direction and hold it. In a typical layout: `controllers` and `security` may import `services`; `services` imports neither. If a shared helper is needed by both, put it at the top level rather than inside one of them.

Do not write your own `__init__.py` — Micronaut generates them for the GraalPy VFS and rejects custom ones.

### 4) Compile, then run — the two fail differently

`pyronaut process` catches type errors, unresolvable annotations and bad generics, and reports them with a file and line. It does **not** catch wrong imports, circular imports, missing beans or dropped annotation arguments. Those need a running context.

Getting `process` to pass is not evidence that anything works. Run `pyronaut dev` or `pyronaut test` before believing it.

## Known traps

| Symptom | Cause |
| --- | --- |
| A constraint or default has no effect | Non-literal annotation argument (§2) |
| `ModuleNotFoundError` at startup | Wrong import path; check the stubs (§1) |
| `ImportError: partially initialized module` | Cross-package cycle (§3) |
| `Custom __init__.py files are not supported` | Delete it; Micronaut generates them |
| Dependency fails to resolve as a jar | POM-only artifact — declare the concrete jars it aggregates |
| `must be static unless ... @TestInstance(Lifecycle.PER_CLASS)` | JUnit-Python lifecycle methods are instance methods; add `TestInstance(TestInstance.Lifecycle.PER_CLASS)` |
| A Java method is unreachable from Python | Its name is a Python keyword. `Pageable.from(...)` needs `getattr(Pageable, "from")` |
| Cannot use a Python exception as an `ExceptionHandler` type parameter | That bound is Java's `Throwable`. Catch it in the controller instead |

## Verification

```bash
pyronaut install     # resolve Java dependencies
pyronaut process     # compile; also writes the OpenAPI document
pyronaut test        # the only step that proves anything runs
```

Docstrings become OpenAPI documentation: the first sentence is the operation `summary`, the whole docstring the `description`. Write them for the person calling the endpoint. Swagger annotations such as `@Tag` are **not** currently honoured.
