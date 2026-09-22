package app;

import io.micronaut.context.ApplicationContextBuilder;
import io.micronaut.context.ApplicationContextConfigurer;
import io.micronaut.context.annotation.ContextConfigurer;
import io.micronaut.core.io.scan.ClassPathResourceLoader;

/**
 * Gives JUnit tests the same classloader the pytest suite already gets.
 *
 * <p>Micronaut Test builds the application context, and its JUnit extension leaves
 * the builder's classloader at the default — the system one — so no project
 * resource directory is reachable and every {@code classpath:} lookup fails.
 * The pytest integration overrides {@code postProcessBuilder} to set the
 * context classloader and a matching resource resolver; the JUnit path has no
 * equivalent, so this configurer supplies it.
 *
 * <p>Without it the server-render bundle is not found and every server-rendered
 * route answers 500 in the browser suite, while the identical pytest suite
 * passes. This is Java rather than Python because it has to be discoverable as
 * an {@code ApplicationContextConfigurer} service before any context exists.
 *
 * <p>Delete once micronaut-projects/pyronaut#169 is fixed.
 */
@ContextConfigurer
public class JUnitClassLoaderConfigurer implements ApplicationContextConfigurer {

    @Override
    public void configure(ApplicationContextBuilder builder) {
        ClassLoader loader = Thread.currentThread().getContextClassLoader();
        if (loader != null) {
            builder.classLoader(loader);
            builder.resourceResolver(ClassPathResourceLoader.defaultLoader(loader));
        }
    }
}
