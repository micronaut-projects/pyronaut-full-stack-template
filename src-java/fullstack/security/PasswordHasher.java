package fullstack.security;

import io.micronaut.core.annotation.Nullable;
import jakarta.inject.Singleton;
import org.bouncycastle.crypto.generators.Argon2BytesGenerator;
import org.bouncycastle.crypto.params.Argon2Parameters;
import org.bouncycastle.util.Arrays;

import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Base64;

/**
 * Hashes and verifies user passwords with Argon2id.
 *
 * <p>Micronaut Security ships no password encoder, so this uses BouncyCastle's Argon2
 * implementation directly: one jar, pure Java, no JNI and no second framework on the class path. A
 * JNI-backed Argon2 binding would add a blocker to a future native image, and GraalJS is already
 * the only one. Argon2id won the Password Hashing Competition and is the current OWASP first
 * choice, where bcrypt is the fallback for platforms that have no Argon2 — see PLAN.md section 7.3.
 *
 * <p>The cost parameters below are OWASP's baseline for Argon2id: 19 MiB of memory, two passes, one
 * lane. Memory is the point of the algorithm — it is what makes a GPU no better at this than a CPU
 * — so raise {@link #MEMORY_KB} before touching anything else, and remember that every concurrent
 * login holds that much at once. {@code p=1} rather than the number of cores because a server is
 * already running these in parallel across requests.
 *
 * <p>A hash is stored in the PHC string format Argon2's own tooling uses:
 *
 * <pre>$argon2id$v=19$m=19456,t=2,p=1$&lt;salt&gt;$&lt;hash&gt;</pre>
 *
 * <p>which carries its own parameters, so a hash written under one configuration keeps verifying
 * after that configuration changes, and {@link #needsRehash(String)} says when the stored
 * parameters are no longer the configured ones. {@code UserService.authenticate} rehashes then,
 * while it still has the password in hand; that reproduces {@code pwdlib}'s
 * {@code verify_and_update} behaviour in the upstream template, so raising a cost parameter later
 * is a configuration change rather than a migration.
 *
 * <p>Base64 is unpadded, as the format specifies. 97 characters at these parameters, which is why
 * {@code users.hashed_password} is {@code VARCHAR(255)}. One hash costs about 25ms warm on an
 * Apple M2 Max, against 138ms for the first one in a JVM.
 *
 * <p>This is Java rather than Python for two reasons. Every line of it is a call into a Java
 * library, so Python was adding a hop and nothing else — the hash itself costs tens of
 * milliseconds, and each of those hops takes an interpreter lock. And as a Java bean it has no
 * context affinity: a pooled Python type may hold it freely, where a Python singleton would pull
 * that type's work back into the one context the singleton lives in. Python calls it exactly as it
 * called the Python version, by importing the type and taking it as a constructor parameter.
 */
@Singleton
public class PasswordHasher {

    /**
     * Memory cost in kibibytes: 19 MiB.
     */
    private static final int MEMORY_KB = 19456;

    /**
     * Passes over memory.
     */
    private static final int ITERATIONS = 2;

    /**
     * Lanes, and the degree of parallelism used to fill them.
     */
    private static final int PARALLELISM = 1;

    private static final int SALT_LENGTH = 16;

    private static final int HASH_LENGTH = 32;

    private static final String ALGORITHM = "argon2id";

    private static final SecureRandom RANDOM = new SecureRandom();

    private static final Base64.Encoder ENCODER = Base64.getEncoder().withoutPadding();

    /**
     * @param rawPassword The password as entered
     * @return The hash to store, in the PHC string format, carrying the parameters that produced it
     */
    public String hash(String rawPassword) {
        byte[] salt = new byte[SALT_LENGTH];
        RANDOM.nextBytes(salt);
        byte[] hash = derive(rawPassword, salt, MEMORY_KB, ITERATIONS, PARALLELISM, HASH_LENGTH);
        return "$" + ALGORITHM
            + "$v=" + Argon2Parameters.ARGON2_VERSION_13
            + "$m=" + MEMORY_KB + ",t=" + ITERATIONS + ",p=" + PARALLELISM
            + "$" + ENCODER.encodeToString(salt)
            + "$" + ENCODER.encodeToString(hash);
    }

    /**
     * Recomputes the hash with the parameters the stored hash was written under, so a hash from an
     * earlier configuration still verifies.
     *
     * @param rawPassword The password as entered, which may be absent
     * @param storedHash The stored hash, which may be absent
     * @return Whether the password matches
     */
    public boolean verify(@Nullable String rawPassword, @Nullable String storedHash) {
        if (rawPassword == null || storedHash == null) {
            return false;
        }
        Encoded encoded = Encoded.parse(storedHash);
        if (encoded == null) {
            return false;
        }
        byte[] computed = derive(
            rawPassword,
            encoded.salt,
            encoded.memoryKb,
            encoded.iterations,
            encoded.parallelism,
            encoded.hash.length
        );
        // Constant time: a comparison that returns early leaks how much of the hash matched.
        return Arrays.constantTimeAreEqual(encoded.hash, computed);
    }

    /**
     * @param storedHash The stored hash
     * @return Whether it should be replaced on the next successful login, because it was written
     *     under parameters other than the configured ones
     */
    public boolean needsRehash(String storedHash) {
        Encoded encoded = Encoded.parse(storedHash);
        return encoded == null
            || encoded.memoryKb != MEMORY_KB
            || encoded.iterations != ITERATIONS
            || encoded.parallelism != PARALLELISM
            || encoded.hash.length != HASH_LENGTH;
    }

    private static byte[] derive(String rawPassword, byte[] salt, int memoryKb, int iterations, int parallelism, int length) {
        Argon2Parameters parameters = new Argon2Parameters.Builder(Argon2Parameters.ARGON2_id)
            .withVersion(Argon2Parameters.ARGON2_VERSION_13)
            .withSalt(salt)
            .withMemoryAsKB(memoryKb)
            .withIterations(iterations)
            .withParallelism(parallelism)
            .build();
        Argon2BytesGenerator generator = new Argon2BytesGenerator();
        generator.init(parameters);
        byte[] hash = new byte[length];
        generator.generateBytes(rawPassword.getBytes(StandardCharsets.UTF_8), hash);
        return hash;
    }

    /**
     * A parsed PHC string. Anything that does not parse as Argon2id version 1.3 is treated as no
     * match rather than as an error: a stored value this cannot read is one no password can verify
     * against, which is the same answer either way.
     */
    private record Encoded(byte[] salt, byte[] hash, int memoryKb, int iterations, int parallelism) {

        @Nullable
        static Encoded parse(String storedHash) {
            String[] parts = storedHash.split("\\$");
            // A leading '$' makes parts[0] empty: "", algorithm, version, parameters, salt, hash.
            if (parts.length != 6 || !ALGORITHM.equals(parts[1])) {
                return null;
            }
            if (!("v=" + Argon2Parameters.ARGON2_VERSION_13).equals(parts[2])) {
                return null;
            }
            int memoryKb = -1;
            int iterations = -1;
            int parallelism = -1;
            for (String parameter : parts[3].split(",")) {
                String[] pair = parameter.split("=", 2);
                if (pair.length != 2) {
                    return null;
                }
                int value;
                try {
                    value = Integer.parseInt(pair[1]);
                } catch (NumberFormatException e) {
                    return null;
                }
                switch (pair[0]) {
                    case "m" -> memoryKb = value;
                    case "t" -> iterations = value;
                    case "p" -> parallelism = value;
                    default -> {
                        return null;
                    }
                }
            }
            if (memoryKb < 1 || iterations < 1 || parallelism < 1) {
                return null;
            }
            try {
                return new Encoded(
                    Base64.getDecoder().decode(parts[4]),
                    Base64.getDecoder().decode(parts[5]),
                    memoryKb,
                    iterations,
                    parallelism
                );
            } catch (IllegalArgumentException e) {
                return null;
            }
        }
    }
}
