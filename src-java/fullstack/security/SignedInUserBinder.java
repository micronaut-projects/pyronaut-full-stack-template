package fullstack.security;

import app.User;
import app.UserRepository;
import io.micronaut.core.convert.ArgumentConversionContext;
import io.micronaut.core.type.Argument;
import io.micronaut.http.HttpRequest;
import io.micronaut.http.bind.binders.PostponedRequestArgumentBinder;
import io.micronaut.http.bind.binders.TypedRequestArgumentBinder;
import io.micronaut.security.authentication.Authentication;
import jakarta.inject.Singleton;

import java.util.Optional;
import java.util.UUID;

/**
 * Binds the signed-in {@link User} to a route parameter of that type.
 *
 * <p>A route says {@code def read_me(user: Annotated[User, Hidden])} and gets the user the
 * session belongs to, the way a parameter of type {@code Authentication} gets the principal.
 * {@code Hidden} is for Micronaut OpenAPI, which would otherwise document the parameter as a query
 * parameter carrying the whole entity.
 *
 * <p>The JWT subject is the user's id as a string. Validating the token does not touch the
 * database — that is the point of a JWT — so the lookup happens here, only for a route that asks
 * for the user, and only once per request. It is a JDBC call, which is why this is a
 * {@link PostponedRequestArgumentBinder}: a postponed binder runs after the filters, on the
 * executor the route runs on, rather than on the event loop with the binders that run first.
 *
 * <p>This only binds; whether the request is allowed was decided by Micronaut Security before it
 * got here. When there is no user to bind — a token whose account no longer exists — the binding is
 * empty and Micronaut reports the unsatisfied argument.
 *
 * <p>Java rather than Python for two reasons. Every line is a Java call, so a Python class would
 * add an interpreter crossing and nothing of its own. And a Python bean implementing a Java
 * interface has to be a singleton, which would put every request that binds a user through the
 * one GraalPy context that singleton lives in, where a Java bean has no context affinity at all.
 *
 * <p>It is also the other direction of the interop: Java injecting something declared in Python.
 * {@code UserRepository} is a {@code Protocol} in {@code app/repositories.py} and {@code User} a
 * dataclass in {@code app/entities.py}; Pyronaut generates a Java type for each, so this is
 * ordinary compilation — rename {@code findById} and this stops compiling.
 */
@Singleton
public class SignedInUserBinder implements TypedRequestArgumentBinder<User>, PostponedRequestArgumentBinder<User> {

    private static final Argument<User> TYPE = Argument.of(User.class);

    private final UserRepository users;

    public SignedInUserBinder(UserRepository users) {
        this.users = users;
    }

    @Override
    public Argument<User> argumentType() {
        return TYPE;
    }

    @Override
    public BindingResult<User> bind(ArgumentConversionContext<User> context, HttpRequest<?> source) {
        Optional<User> user = source.getUserPrincipal(Authentication.class).flatMap(this::find);
        return user.isPresent() ? () -> user : BindingResult.empty();
    }

    private Optional<User> find(Authentication authentication) {
        try {
            return users.findById(UUID.fromString(authentication.getName()));
        } catch (IllegalArgumentException e) {
            // This application issues the tokens it reads, so a subject that is not a user id
            // identifies nobody, the same as an id that no longer resolves.
            return Optional.empty();
        }
    }
}
