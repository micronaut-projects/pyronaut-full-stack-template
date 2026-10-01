"""Logging configuration.

Pyronaut routes Python's ``logging`` module onto Logback, so the standard
``dictConfig`` shape configures the whole application — Micronaut's own loggers
included.

The format below reproduces the pattern Pyronaut uses before this module runs,
because ``dictConfig`` replaces that appender rather than adding to it: whatever
is configured here applies from the first record Python's import of this module
makes it to, and everything logged earlier — the launcher, the GraalPy engine —
has already gone out under the default. A format that differs is visible as
output that changes shape partway through startup.

Two things make the reproduction possible. Each ``%(name)s`` token is translated
to a Logback conversion word (``asctime`` to ``%d{yyyy-MM-dd HH:mm:ss.SSS}``,
``message`` to ``%msg``, and so on), and everything else in the string is passed
through to the pattern as written — so Logback's own conversion words work here,
which is where the colour comes from. ``%logger{36}`` is one of those: there is
no ``%(name)s`` spelling for the abbreviated logger name, since ``%(name)s``
becomes an unabbreviated ``%logger``. ``%n`` is appended for you; adding one
ends every record with a blank line.

Logback's colour words emit ANSI escapes whether or not the output is a
terminal, so a redirected log contains them either way. That is true of the
default pattern as well, which is the point: one shape throughout.
"""

from logback.config import dictConfig

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%cyan(%(asctime)s) %gray([%(levelname)s]) %magenta(%logger{36}): %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "standard",
            "stream": "ext://sys.stdout",
        }
    },
    "root": {"level": "INFO", "handlers": ["console"]},
    "loggers": {
        # Set to TRACE to print the resolved HTTP routes at startup.
        "io.micronaut.web.router": {"level": "INFO", "handlers": ["console"]},
    },
}

dictConfig(LOGGING)
