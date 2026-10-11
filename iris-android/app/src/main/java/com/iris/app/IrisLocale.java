package com.iris.app;

import android.content.Context;
import android.content.res.Configuration;

import java.util.Locale;

/**
 * In-app language resolution shared by every entry point.
 *
 * English is the source of truth: values/strings.xml holds the base copy and each
 * values-XX folder overrides key-by-key, so a missing translation degrades to English
 * instead of an empty label - the same contract as the extension's i18n.js. The eight
 * languages and their native labels mirror IRIS_LANGUAGES so both selectors read as
 * one list across platforms.
 */
final class IrisLocale {
    /** {code, native label} pairs in selector order. Native labels are never translated. */
    static final String[][] LANGUAGES = {
        {"en", "English"},
        {"tl", "Tagalog"},
        {"zh", "\u4e2d\u6587"},
        {"ja", "\u65e5\u672c\u8a9e"},
        {"fr", "Fran\u00e7ais"},
        {"es", "Espa\u00f1ol"},
        {"ar", "\u0627\u0644\u0639\u0631\u0628\u064a\u0629"},
        {"hi", "\u0939\u093f\u0928\u094d\u092f\u0940"},
    };

    static final String DEFAULT = "en";

    /**
     * Captured at class load, which always runs before the first wrap() can call
     * Locale.setDefault - so "system language" can never be poisoned by an earlier
     * in-app pick within the same process.
     */
    private static final Locale SYSTEM = Locale.getDefault();

    private IrisLocale() {}

    /** The language the app should render in: the saved choice, else the system locale. */
    static String get(Context context) {
        String saved = IrisPrefs.getUiLanguage(context);
        if (saved != null && isSupported(saved)) return saved;
        return resolveSystem(SYSTEM);
    }

    static boolean isSupported(String code) {
        for (String[] language : LANGUAGES) {
            if (language[0].equals(code)) return true;
        }
        return false;
    }

    /**
     * Filipino phones report "fil" while the Tagalog resources live under "tl",
     * and any other system language falls back to English - per-key fallback
     * never starts from a locale we do not ship.
     */
    static String resolveSystem(Locale system) {
        String lang = system.getLanguage();
        if ("fil".equals(lang)) return "tl";
        return isSupported(lang) ? lang : DEFAULT;
    }

    static String label(String code) {
        for (String[] language : LANGUAGES) {
            if (language[0].equals(code)) return language[1];
        }
        return LANGUAGES[0][1];
    }

    /**
     * Attaches the chosen language to a Context that is created once - every Activity
     * and the Service - so getString resolves in the app language rather than the
     * system one. recreate() on a language change re-runs this for Activities.
     */
    static Context wrap(Context base) {
        Locale locale = new Locale(get(base));
        Locale.setDefault(locale);
        Configuration config = new Configuration(base.getResources().getConfiguration());
        config.setLocale(locale);
        config.setLayoutDirection(locale);
        return base.createConfigurationContext(config);
    }

    /**
     * Re-applies the language to a Context that attached before the reader picked a
     * new one. A running OverlayService cannot re-run attachBaseContext, and restarting
     * it would run onDestroy - which marks the bubble disabled and could strand it
     * (see OverlayService.applyOverlayTheme) - so the service refreshes its resources
     * in place at the top of every onStartCommand instead.
     */
    @SuppressWarnings("deprecation")
    static void apply(Context context) {
        Locale locale = new Locale(get(context));
        Locale.setDefault(locale);
        Configuration config = new Configuration(context.getResources().getConfiguration());
        config.setLocale(locale);
        config.setLayoutDirection(locale);
        context.getResources().updateConfiguration(config, context.getResources().getDisplayMetrics());
    }
}
