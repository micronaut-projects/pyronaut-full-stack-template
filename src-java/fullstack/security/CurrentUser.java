package fullstack.security;

import app.User;
import app.services.UserService;
import io.micronaut.core.annotation.Nullable;
import io.micronaut.security.authentication.Authentication;
import jakarta.inject.Singleton;

import java.util.UUID;

/**
 * Resolves the authenticated principal to a {@link User}.
 *
 * <p>The JWT subject is the user's id as a string, so every route that needs the signed-in user has
 * to look it up. A bean rather than a helper function because it needs {@link UserService}, and the
 * route modules that use it are modules — there is no constructor to thread a dependency through.
 *
 * <p>This is the other direction of the interop: a Java bean injecting a Python one. {@code
 * UserService} is a Python class in {@code app/services/users.py} and {@code User} a Python entity,
 * and both are ordinary Java types here — Pyronaut generates a Java class for each, so the Java
 * compiler sees {@code by_id(UUID)} returning a {@code User} and the container injects the same bean
 * a Python constructor parameter would have received. Nothing is reflective and nothing is stringly
 * typed: rename the Python method and this stops compiling.
 *
 * <p>Being Java also makes it free of context affinity, which a bean held by the pooled route modules
 * wants to be. It holds a Python bean, but a reference to one is not the same as being one: the
 * generated {@code UserService} resolves to the instance of whichever context is serving the call.
 */
@Singleton
public class CurrentUser {

    private final UserService users;

    public CurrentUser(UserService users) {
        this.users = users;
    }

    /**
     * The signed-in user.
     *
     * <p>{@link Authentication#getName()} is the subject: a string, so it is parsed rather than
     * handed straight to the repository. A subject that is not a user id is treated the same way as
     * one that no longer resolves — this application issues the tokens it reads, so either means the
     * caller cannot be identified.
     *
     * @param authentication The authentication of the current request
     * @return The user, or {@code null} if the subject does not resolve to one
     */
    @Nullable
    public User of(Authentication authentication) {
        UUID id;
        try {
            id = UUID.fromString(authentication.getName());
        } catch (IllegalArgumentException e) {
            return null;
        }
        return users.by_id(id);
    }
}
