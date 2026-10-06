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
5. Reach for Java only where it removes a hop.

### 1) Check the generated stubs before guessing an import

`__pyronaut__/ide-stubs/` is generated from the actual classpath and is the authoritative answer to "where does this class live". Grep it rather than inferring from the Java package:

```bash
grep -rn "class StartupEvent" __pyronaut__/ide-stubs/
```

Java packages map by dropping a leading `io.`: `io.micronaut.http` → `micronaut.http`, `io.swagger.v3...` → `swagger.v3...`. But the mapping does not tell you which *module* a class ended up in. `StartupEvent` and `ApplicationEventListener` are in `micronaut.context.event`, not `micronaut.runtime.event`, and only the stubs say so.

A wrong import compiles and fails at context startup with `ModuleNotFoundError`, usually reported against whichever bean was being constructed rather than the module with the bad import.

### 2) Write annotations with literal arguments only

The processor reads annotations from source; it does not evaluate them. Since Core 5.2.9 ([micronaut-core#13366](https://github.com/micronaut-projects/micronaut-core/pull/13366)) an argument it cannot read **fails the build** and names the fix. Before that it was discarded without a warning, which made this the worst trap in the model: a dropped `Size` on a password field compiled, started and served.

```python
# FAILS PROCESSING — "[PASSWORD] ... is a name bound to [Size(min=8, max=128)],
# not an annotation ... Write the annotation inline."
PASSWORD = Size(min=8, max=128)
password: Annotated[str, NotBlank, PASSWORD]

# FAILS PROCESSING — "The value [str(DEFAULT_SIZE)] of member [defaultValue] of
# @QueryValue is not a compile-time constant ... use a literal."
size: Annotated[int, QueryValue(defaultValue=str(DEFAULT_SIZE))] = DEFAULT_SIZE

# RIGHT
password: Annotated[str, NotBlank, Size(min=8, max=128, message="...")]
size: Annotated[int, QueryValue(defaultValue="100")] = DEFAULT_SIZE

# ALSO RIGHT — a bare name for a *scalar* argument resolves, and always did.
# Measured on 0.0.6: `minLength: 8` reaches the OpenAPI document.
password: Annotated[str, NotBlank, Size(min=MIN_PASSWORD, max=128)]
```

So the failure mode is now loud. Write an annotation inline rather than binding it to a name, and do not compute an argument — but a constant for a scalar argument is fine. On an older Core, treat this as the silent-failure rule it used to be and add a test that asserts the constraint rejects bad input.

### 3) Keep cross-package imports one-directional

Micronaut generates a package `__init__.py` that eagerly imports **every** module in the package. Two packages that import from each other therefore deadlock at context startup, even when the individual modules would be fine.

Establish a direction and hold it. In a typical layout: `controllers` and `security` may import `services`; `services` imports neither. If a shared helper is needed by both, put it at the top level rather than inside one of them.

Do not write your own `__init__.py` — Micronaut generates them for the GraalPy VFS and rejects custom ones.

### 4) Compile, then run — the two fail differently

`pyronaut process` catches type errors, unresolvable annotations and bad generics, and reports them with a file and line. It does **not** catch wrong imports, circular imports, missing beans or dropped annotation arguments. Those need a running context.

Getting `process` to pass is not evidence that anything works. Run `pyronaut dev` or `pyronaut test` before believing it.

### 5) Reach for Java only where it removes a hop

A Pyronaut project has a Java source root as well (`java` under `[tool.pyronaut.sources]`, `src-java`
by default), compiled into the same container. Both directions work and neither is reflective.

```python
from myapp.security import PasswordHasher     # a Java class, imported by its Java package

@Singleton
class UserService:
    def __init__(self, passwords: PasswordHasher):
```

```java
// Java injecting a Python bean, through the class Pyronaut generates for it
public SignedInUserBinder(UserRepository users) { this.users = users; }

private Optional<User> find(Authentication authentication) {
    return users.findById(UUID.fromString(authentication.getName()));
}
```

`SignedInUserBinder` is what lets a route take the signed-in user as a parameter.
Declare it `user: Annotated[User, Hidden]`: without `Hidden`, Micronaut OpenAPI documents it as a
required query parameter carrying the whole entity. A type alias for that annotation does not work —
the processor does not resolve it, and the parameter becomes an unbindable `Object`.

Micronaut's extension points can be implemented in Python as well — a `@ServerFilter` class, a
`TypedRequestArgumentBinder[User]`, a `GenericJwtClaimsValidator` — but such a bean has to be a
singleton: a `@ContextPooled` class is generated without the Java interfaces it declares, so a
pooled binder fails at startup with a `ClassCastException`. A singleton runs in one GraalPy
context, which for something that runs on every request is the reason the binder is Java.

An entity bound as a route parameter arrives as the Python dataclass, with a `uuid.UUID` id. One a
repository returned is still the Java object, and `str()` of its id is `UUID('...')`. Comparing the
two with `str(a.id) == str(b.id)` is wrong without complaint; use `same_id` from `app/ids.py`.

Two reasons to move a bean to Java, and "Java is faster" is not one of them at this granularity:

- **Its body is already Java.** A Python bean whose every line calls into a Java library pays an
  interpreter crossing per call and adds nothing of its own. A password encoder is the archetype.
- **A Java bean has no context affinity.** A pooled Python type — every route module is one — can
  hold a Java bean freely. Holding a Python *singleton* instead puts that type's work back through
  the one context the singleton lives in, which is the cost pooling exists to avoid, and a recent
  Core warns about it during processing.

Keep the Java side small: a bean holding application logic belongs in Python even when it touches
Java libraries.

Give the Java code a package of its own, not the one the generated stubs use — that package mirrors
the Python root package, so `from app import Thing` has a Python package of that name to resolve
against, and an import meant for the Java class would be reading a name from the Python package
instead. A separate package leaves no room for the question.

## Known traps

| Symptom | Cause |
| --- | --- |
| A constraint or default has no effect | Non-literal annotation argument (§2) |
| `ModuleNotFoundError` at startup | Wrong import path; check the stubs (§1) |
| `ImportError: partially initialized module` | Cross-package cycle (§3) |
| `Custom __init__.py files are not supported` | Delete it; Micronaut generates them |
| Dependency fails to resolve as a jar | POM-only artifact — declare the concrete jars it aggregates |
| `must be static unless ... @TestInstance(Lifecycle.PER_CLASS)` | JUnit-Python lifecycle methods are instance methods; add `TestInstance(TestInstance.Lifecycle.PER_CLASS)` |
| A Java member is unreachable from Python | Its name is a Python keyword, so it takes a trailing underscore: `Pageable.from(...)` is written `Pageable.from_(...)` |
| `Cannot import [Mapping] ... is not on the compile classpath` | A nested Java annotation has no top-level type. Reach it through its enclosing type: `@Mapper.Mapping(...)` |
| Cannot use a Python exception as an `ExceptionHandler` type parameter | That bound is Java's `Throwable`. Catch it in the controller instead |
| A Java class in `src-java` is not found by a Python import | Its package is the one the generated stubs use, which mirrors a Python package of the same name (§5). Give the Java code its own package |

## Verification

```bash
pyronaut install     # resolve Java dependencies
pyronaut process     # compile; also writes the OpenAPI document
pyronaut test        # the only step that proves anything runs
```

Docstrings become OpenAPI documentation: the first sentence is the operation `summary`, the whole docstring the `description`. Write them for the person calling the endpoint. Swagger annotations such as `@Tag` work as well, since Core 5.2.5 ([micronaut-core#13345](https://github.com/micronaut-projects/micronaut-core/pull/13345)) — before that the compiler could not resolve any `io.`-prefixed package other than `io.micronaut`, and they were dropped silently.

Operation ids must be unique across the whole API. A collision is not an error: Micronaut OpenAPI appends a number, and a generated client grows a `signup1` whose digit depends on declaration order.
