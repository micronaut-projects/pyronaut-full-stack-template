package fullstack.security;

import io.micronaut.context.annotation.Replaces;
import io.micronaut.core.annotation.Nullable;
import io.micronaut.http.HttpRequest;
import io.micronaut.http.HttpResponse;
import io.micronaut.http.MediaType;
import io.micronaut.http.MutableHttpResponse;
import io.micronaut.http.server.exceptions.response.ErrorResponseProcessor;
import io.micronaut.security.authentication.AuthorizationException;
import io.micronaut.security.authentication.DefaultAuthorizationExceptionHandler;
import io.micronaut.security.authentication.WwwAuthenticateChallengeProvider;
import io.micronaut.security.config.RedirectConfiguration;
import io.micronaut.security.config.RedirectService;
import io.micronaut.security.errors.PriorToLoginPersistence;
import jakarta.inject.Singleton;

import java.net.URI;
import java.util.List;

/**
 * Sends a signed-out browser to the login page, and leaves every other caller alone.
 *
 * <p>Without this, opening <code>/</code> signed out answers 401 with an error body, which is the
 * right answer for an API client and a dead end for a person.
 *
 * <p>The obvious way to get the redirect is {@code micronaut.security.redirect.enabled}, and it is
 * the wrong one here. That switch is global: {@code CookieLoginHandler} reads the same flag in its
 * constructor and, when it is on, answers a *failed login* with 303 to {@code login-failure}
 * instead of 401. Any client that follows redirects — including {@code fetch} — would then see the
 * login page and a 200, making a rejected password indistinguishable from an accepted one.
 * {@code config/application.toml} keeps the flag off for that reason, and this handler covers the
 * one case the flag was wanted for.
 *
 * <p>The test is the {@code Accept} header rather than the path, which is how Micronaut's own
 * handler decides when redirects are enabled: a browser navigating to a page asks for
 * {@code text/html}, while {@code fetch} from the hydrated client and the pytest suite do not, so
 * they keep their 401. Only an unauthenticated request redirects — a signed-in user who is merely
 * not allowed (a non-superuser opening {@code /admin}) still gets 403, because sending them to a
 * login page they are already past would be a loop that explains nothing.
 */
@Singleton
@Replaces(DefaultAuthorizationExceptionHandler.class)
public class PageRedirectAuthorizationHandler extends DefaultAuthorizationExceptionHandler {

    private static final URI LOGIN = URI.create("/login");

    public PageRedirectAuthorizationHandler(
        ErrorResponseProcessor<?> errorResponseProcessor,
        RedirectConfiguration redirectConfiguration,
        RedirectService redirectService,
        List<WwwAuthenticateChallengeProvider<HttpRequest<?>>> wwwAuthenticateChallengeProviders,
        // Optional, and absent here: nothing in this application remembers where an
        // unauthenticated request was headed. Without @Nullable the bean fails to
        // construct, and a broken exception handler reports itself as 500 on every
        // route that needed a session.
        @Nullable PriorToLoginPersistence priorToLoginPersistence
    ) {
        super(
            errorResponseProcessor,
            redirectConfiguration,
            redirectService,
            wwwAuthenticateChallengeProviders,
            priorToLoginPersistence
        );
    }

    @Override
    public MutableHttpResponse<?> handle(HttpRequest request, AuthorizationException exception) {
        if (!exception.isForbidden() && acceptsHtml(request)) {
            return HttpResponse.seeOther(LOGIN);
        }
        return super.handle(request, exception);
    }

    private static boolean acceptsHtml(HttpRequest<?> request) {
        return request.getHeaders().accept().stream().anyMatch(MediaType.TEXT_HTML_TYPE::equals);
    }
}
