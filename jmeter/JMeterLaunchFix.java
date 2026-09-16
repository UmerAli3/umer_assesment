import java.lang.reflect.*;
import java.net.URLClassLoader;

/**
 * Fixes a known version-mismatch bug: this system's JMeter 2.13 package
 * (org.apache.jmeter.save.SaveService) was built against an old XStream
 * API (pre security-whitelist era), but Ubuntu's system libxstream-java
 * (1.4.20) enforces a deny-by-default whitelist. JMeter's own code never
 * calls XStream.addPermission(...) because that API didn't exist for
 * security purposes when JMeter 2.13 was written, so loading a .jmx plan
 * throws ForbiddenClassException.
 *
 * This launcher loads JMeter's own DynamicClassLoader (the exact
 * classloader JMeter's real engine will use), forces SaveService's static
 * initializer to run inside it, grabs the already-constructed XStream
 * instances (JMXSAVER/JTLSAVER), and grants them full permission before
 * calling into the real JMeter entry point. No bytecode is modified -
 * this only calls the same addPermission() API JMeter itself would call
 * if it had been built against a newer XStream.
 */
public class JMeterLaunchFix {
    public static void main(String[] args) throws Exception {
        Class<?> newDriverClass = Class.forName("org.apache.jmeter.NewDriver");

        Field loaderField = newDriverClass.getDeclaredField("loader");
        loaderField.setAccessible(true);
        URLClassLoader loader = (URLClassLoader) loaderField.get(null);

        Thread.currentThread().setContextClassLoader(loader);

        // JMeterUtils normally has its home set up inside NewDriver.main()/JMeter.start()
        // before anything touches SaveService. We're forcing SaveService to load early,
        // so set it explicitly first using the same classloader.
        Class<?> jmeterUtilsClass = Class.forName("org.apache.jmeter.util.JMeterUtils", true, loader);
        Method setJMeterHome = jmeterUtilsClass.getMethod("setJMeterHome", String.class);
        String jmHome = System.getProperty("jmeter.home", "/usr/share/jmeter");
        setJMeterHome.invoke(null, jmHome);

        Class<?> saveServiceClass = Class.forName("org.apache.jmeter.save.SaveService", true, loader);
        Class<?> xstreamClass = Class.forName("com.thoughtworks.xstream.XStream", true, loader);
        Class<?> permissionClass = Class.forName("com.thoughtworks.xstream.security.TypePermission", true, loader);
        Class<?> anyTypePermissionClass = Class.forName("com.thoughtworks.xstream.security.AnyTypePermission", true, loader);

        Field anyField = anyTypePermissionClass.getField("ANY");
        Object anyPermission = anyField.get(null);

        Method addPermission = xstreamClass.getMethod("addPermission", permissionClass);

        for (String fieldName : new String[]{"JMXSAVER", "JTLSAVER"}) {
            try {
                Field f = saveServiceClass.getDeclaredField(fieldName);
                f.setAccessible(true);
                Object xstreamInstance = f.get(null);
                addPermission.invoke(xstreamInstance, anyPermission);
                System.err.println("[JMeterLaunchFix] Patched permissions on " + fieldName);
            } catch (NoSuchFieldException e) {
                // field name may differ across builds; skip if absent
            }
        }

        Method mainMethod = newDriverClass.getMethod("main", String[].class);
        mainMethod.invoke(null, (Object) args);
    }
}
