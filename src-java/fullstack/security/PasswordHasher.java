package fullstack.security;

import io.micronaut.core.annotation.Nullable;
import jakarta.inject.Singleton;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.factory.PasswordEncoderFactories;
import org.springframework.security.crypto.password.PasswordEncoder;

/**
 * Hashes and verifies user passwords.
 *
 * <p>Micronaut Security ships no password encoder, so this uses Spring Security Crypto's. It is a
 * standalone artifact — no Spring context, no Spring Boot, no auto-configuration — and it is pure
 * Java with no JNI, which matters here: a JNI-backed Argon2 binding would add a second blocker to a
 * future native image, and GraalJS is already the only one. See PLAN.md section 7.3, and the
 * Micronaut guide "Building a REST API — Spring Boot vs Micronaut: Security Basic Auth", which uses
 * the same pairing.
 *
 * <p>{@code DelegatingPasswordEncoder} stores an {@code {id}} prefix with each hash and lets an
 * older scheme be re-encoded on a successful login. That reproduces {@code pwdlib}'s
 * {@code verify_and_update} behaviour in the upstream template, so an algorithm change later is a
 * configuration change rather than a migration.
 *
 * <p>This is Java rather than Python for two reasons. Every line of it is a call into a Java
 * library, so Python was adding a hop and nothing else — bcrypt itself costs milliseconds, and each
 * of those hops takes an interpreter lock. And as a Java bean it has no context affinity: a pooled
 * Python type may hold it freely, where a Python singleton would pull that type's work back into the
 * one context the singleton lives in. Python calls it exactly as it called the Python version, by
 * importing the type and taking it as a constructor parameter.
 */
@Singleton
public class PasswordHasher {

    /**
     * Encodes as bcrypt; still verifies any scheme the delegating encoder knows, so hashes written
     * by an earlier configuration keep working.
     */
    private final PasswordEncoder encoder = PasswordEncoderFactories.createDelegatingPasswordEncoder();

    private final BCryptPasswordEncoder bcrypt = new BCryptPasswordEncoder();

    /**
     * @param rawPassword The password as entered
     * @return The hash to store, carrying the {@code {id}} prefix of the scheme that produced it
     */
    public String hash(String rawPassword) {
        return encoder.encode(rawPassword);
    }

    /**
     * @param rawPassword The password as entered, which may be absent
     * @param storedHash The stored hash, which may be absent
     * @return Whether the password matches
     */
    public boolean verify(@Nullable String rawPassword, @Nullable String storedHash) {
        if (rawPassword == null || storedHash == null) {
            return false;
        }
        if (storedHash.startsWith("{")) {
            return encoder.matches(rawPassword, storedHash);
        }
        // A hash written before the delegating prefix was introduced.
        return bcrypt.matches(rawPassword, storedHash);
    }

    /**
     * @param storedHash The stored hash
     * @return Whether it should be replaced on the next successful login
     */
    public boolean needsRehash(String storedHash) {
        return !storedHash.startsWith("{bcrypt}");
    }
}
