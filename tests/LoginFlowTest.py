"""End-to-end browser tests: Playwright Java, driven from Python.

A JUnit 5 test written as a Python module. `MicronautTest()` at module level
hands the file to the JUnit engine, and `[tool.pyronaut.test] engine = "both"`
runs it in the same `pyronaut test` invocation as the pytest API suite —
against the same embedded server, with the same MySQL container.

That is the part worth noticing. The upstream FastAPI template runs Playwright
separately, against a Vite dev server, with `PLAYWRIGHT_BASE_URL` plumbing to
connect the two. Here the application under test *is* the one the API tests
use: one command, one process, no separate frontend server.

Playwright is driven through its plain API rather than the `@UsePlaywright`
JUnit extension, because the extension delivers `Page` by parameter injection
and Pyronaut's JUnit-Python modules take their injections at module level. The
lifecycle is explicit instead, which is a small price and easy to read.
"""

from typing import Annotated

from com.microsoft.playwright import Playwright
from jakarta.inject import Inject
from micronaut.runtime.server import EmbeddedServer
from micronaut.test.extensions.junit5.annotation import MicronautTest
from org.junit.jupiter.api import AfterAll, BeforeAll, Test, TestInstance

MicronautTest()
# @BeforeAll and @AfterAll are instance methods here, not static ones, so JUnit
# needs the per-class lifecycle or discovery fails outright. Without it the
# browser would have to be launched per test, which costs seconds each time.
TestInstance(TestInstance.Lifecycle.PER_CLASS)

embedded_server: Annotated[EmbeddedServer, Inject]

SUPERUSER_EMAIL = "admin@example.com"
SUPERUSER_PASSWORD = "testpassword123"

_playwright = None
_browser = None


@BeforeAll
def start_browser():
    global _playwright, _browser
    _playwright = Playwright.create()
    _browser = _playwright.chromium().launch()


@AfterAll
def stop_browser():
    if _browser is not None:
        _browser.close()
    if _playwright is not None:
        _playwright.close()


def _base_url() -> str:
    return str(embedded_server.getURL())


def _new_page():
    return _browser.newContext().newPage()


def _sign_in(page):
    page.navigate(f"{_base_url()}/login")
    page.fill("[data-testid='email-input']", SUPERUSER_EMAIL)
    page.fill("[data-testid='password-input']", SUPERUSER_PASSWORD)
    page.click("[data-testid='login-submit']")
    try:
        page.waitForURL(f"{_base_url()}/")
    except Exception as failure:
        raise AssertionError(
            f"sign-in did not reach the dashboard. url={page.url()} "
            f"body={str(page.content())[:400]}"
        ) from failure


@Test
def test_the_login_page_is_server_rendered():
    """The form must be in the HTML before any JavaScript runs.

    That is the difference between server rendering and a client-side app: the
    markup arrives complete, and hydration only makes it interactive.
    """
    page = _new_page()
    try:
        response = page.navigate(f"{_base_url()}/login")
        assert response.status() == 200, (
            f"GET /login returned {response.status()}: {str(page.content())[:600]}"
        )
        assert "Log in" in str(page.textContent("h1"))
        assert page.locator("[data-testid='login-submit']").count() == 1
    finally:
        page.close()


@Test
def test_sign_in_reaches_the_dashboard():
    """Signing in lands on the dashboard, greeted by name.

    The greeting is asserted by shape rather than by content: the API suite
    renames the superuser, and with the Test Resources container shared across
    runs that change outlives the test. Depending on a specific name here would
    make this pass or fail according to what ran before it.
    """
    page = _new_page()
    try:
        _sign_in(page)
        greeting = str(page.textContent("h1"))
        assert greeting.startswith("Hi, "), f"dashboard heading was {greeting!r}"
        # The navigation only renders for a signed-in user.
        assert page.locator("[data-testid='logout-button']").count() == 1
    finally:
        page.close()


@Test
def test_an_unknown_password_keeps_you_on_the_login_page():
    page = _new_page()
    try:
        page.navigate(f"{_base_url()}/login")
        page.fill("[data-testid='email-input']", SUPERUSER_EMAIL)
        page.fill("[data-testid='password-input']", "not-the-password")
        page.click("[data-testid='login-submit']")
        page.waitForSelector(".alert-error")
        assert "Incorrect email or password" in str(page.textContent(".alert-error"))
    finally:
        page.close()


@Test
def test_the_hydration_bundle_is_served():
    """Without this the page renders but never becomes interactive.

    A server-rendered form with no JavaScript still submits — natively, to the
    wrong place — so a missing bundle shows up as a mysterious timeout rather
    than an obvious error.
    """
    page = _new_page()
    try:
        response = page.request().get(f"{_base_url()}/static/client.js")
        assert response.status() == 200, (
            f"GET /static/client.js returned {response.status()}"
        )
    finally:
        page.close()


@Test
def test_the_dashboard_sends_a_signed_out_browser_to_the_login_page():
    """A person gets the login page; an API client still gets 401.

    Both halves matter. The redirect comes from `PageRedirectAuthorizationHandler`,
    which keys off `Accept: text/html` precisely so that it cannot reach the API —
    and the API answering 303 instead of 401 is what the hydrated client would
    silently mistake for a successful call.
    """
    page = _new_page()
    try:
        response = page.navigate(f"{_base_url()}/")
        assert response.status() == 200, (
            f"expected the login page, got {response.status()}"
        )
        assert page.url().rstrip("/").endswith("/login"), (
            f"signed-out dashboard did not reach the login page. url={page.url()}"
        )

        api = page.request().get(f"{_base_url()}/api/v1/users/me")
        assert api.status() == 401, (
            f"the API must stay 401 for an unauthenticated caller, got {api.status()}"
        )
    finally:
        page.close()


@Test
def test_an_item_can_be_added_from_the_browser():
    """Exercises the hydrated client: the form posts to the API and re-renders."""
    page = _new_page()
    try:
        _sign_in(page)
        page.navigate(f"{_base_url()}/items")
        page.fill("[data-testid='title-input']", "Added from a browser")
        page.click("[data-testid='add-item']")
        page.waitForSelector("[data-testid='items-table']")
        assert "Added from a browser" in str(page.textContent("[data-testid='items-table']"))
    finally:
        page.close()
