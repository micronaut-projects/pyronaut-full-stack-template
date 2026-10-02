"""Spike: can Playwright Java be driven from Python?

It was the largest unknown in this port, and the answer is yes — `LoginFlowTest`
drives a real browser through the application on the strength of it. This stays
as the smallest possible test — launch Chromium, set some content, read it back
— so that a failure points at the interop rather than at the application.

It is a JUnit 5 test written as a Python module, not a pytest: `MicronautTest()`
at module level hands the file to the JUnit engine, and `[tool.pyronaut.test]
engine = "both"` lets it run in the same `pyronaut test` invocation as the
pytest API suite.

What it is probing:
  - `Playwright.create()` spawns a Node driver subprocess and speaks to it over
    pipes. Does that work from GraalPy?
  - Playwright's API is heavily overloaded and uses nested `Options` builders.
    Does GraalPy pick the right overloads?
"""

from com.microsoft.playwright import Playwright
from micronaut.test.extensions.junit5.annotation import MicronautTest
from org.junit.jupiter.api import Test

MicronautTest(start_application=False)


@Test
def test_chromium_launches_and_renders():
    playwright = Playwright.create()
    try:
        browser = playwright.chromium().launch()
        try:
            page = browser.newPage()
            page.setContent("<h1 id='greeting'>Hello from Pyronaut</h1>")
            assert "Hello from Pyronaut" in str(page.content())
            assert str(page.textContent("#greeting")) == "Hello from Pyronaut"
        finally:
            browser.close()
    finally:
        playwright.close()
