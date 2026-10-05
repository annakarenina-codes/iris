package com.iris.app;

import android.content.Context;
import android.content.SharedPreferences;

final class IrisPrefs {
    private static final String PREFS = "iris_settings";
    private static final String BACKEND_URL = "backend_url";
    private static final String BACKEND_URL_BUILT_IN = "backend_url_built_in";
    private static final String BUBBLE_ENABLED = "bubble_enabled";
    private static final String BUBBLE_X = "bubble_x";
    private static final String BUBBLE_Y = "bubble_y";
    private static final String THEME = "irisTheme";
    /** Matches the extension's irisUiLanguage key; null means follow the system locale. */
    private static final String UI_LANGUAGE = "irisUiLanguage";
    // Bring-your-own-key, exactly like the extension's sightengineApiUser/Secret settings:
    // the credentials live on the device and never ship in code or on a server.
    private static final String SIGHTENGINE_API_USER = "sightengine_api_user";
    private static final String SIGHTENGINE_API_SECRET = "sightengine_api_secret";
    // Auto-filling the paste panel reads the clipboard the moment the panel opens, so the
    // choice is opt-in and off by default: a reader who never turns it on keeps the
    // tap-Paste-only behavior, exactly as the privacy copy promises.
    private static final String CLIPBOARD_AUTO_OPEN = "clipboard_auto_open";
    private static final String DEFAULT_BACKEND_URL = "https://iris-production-8342.up.railway.app"; // iris:backend-url

    private IrisPrefs() {}

    /**
     * Whether the backend card belongs on screen.
     *
     * While the built-in address still points at a development machine, whoever is running
     * IRIS needs to be able to type the real one. Once a hosted address is built in, the
     * people taking part in the study have no reason to see the field, and every reason not
     * to change it by accident.
     */
    static boolean isBackendConfigurable() {
        return DEFAULT_BACKEND_URL.contains("10.0.2.2")
            || DEFAULT_BACKEND_URL.contains("127.0.0.1")
            || DEFAULT_BACKEND_URL.contains("localhost");
    }

    static String getBackendUrl(Context context) {
        SharedPreferences settings = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String saved = settings.getString(BACKEND_URL, null);
        String savedAgainst = settings.getString(BACKEND_URL_BUILT_IN, null);

        // An address that was typed in belongs to the build it was typed into. When the
        // built-in address changes -- a new deployment, or a move off the emulator -- an
        // address saved against the old one is stale, and on a build where the backend card
        // is hidden there would be no way left to correct it.
        if (saved == null || !DEFAULT_BACKEND_URL.equals(savedAgainst)) {
            return DEFAULT_BACKEND_URL;
        }

        return saved;
    }

    static void setBackendUrl(Context context, String value) {
        String cleaned = value == null ? DEFAULT_BACKEND_URL : value.trim().replaceAll("/+$", "");
        if (cleaned.isEmpty()) cleaned = DEFAULT_BACKEND_URL;

        SharedPreferences.Editor editor = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit();
        editor.putString(BACKEND_URL, cleaned);
        editor.putString(BACKEND_URL_BUILT_IN, DEFAULT_BACKEND_URL);
        editor.apply();
    }

    static boolean isBubbleEnabled(Context context) {
        return context
            .getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getBoolean(BUBBLE_ENABLED, false);
    }

    static void setBubbleEnabled(Context context, boolean enabled) {
        SharedPreferences.Editor editor = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit();
        editor.putBoolean(BUBBLE_ENABLED, enabled);
        editor.apply();
    }

    static int getBubbleX(Context context, int fallback) {
        return context
            .getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getInt(BUBBLE_X, fallback);
    }

    static int getBubbleY(Context context, int fallback) {
        return context
            .getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getInt(BUBBLE_Y, fallback);
    }

    static void setBubblePosition(Context context, int x, int y) {
        SharedPreferences.Editor editor = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit();
        editor.putInt(BUBBLE_X, x);
        editor.putInt(BUBBLE_Y, y);
        editor.apply();
    }

    /** Matches the extension's irisTheme key and its system/light/dark values. */
    static String getTheme(Context context) {
        return context
            .getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(THEME, IrisUi.THEME_SYSTEM);
    }

    static void setTheme(Context context, String theme) {
        SharedPreferences.Editor editor = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit();
        editor.putString(THEME, theme);
        editor.apply();
    }

    /** The chosen app language, or null when the reader has never picked one. */
    static String getUiLanguage(Context context) {
        return context
            .getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(UI_LANGUAGE, null);
    }

    static void setUiLanguage(Context context, String code) {
        SharedPreferences.Editor editor = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit();
        if (code == null) {
            editor.remove(UI_LANGUAGE);
        } else {
            editor.putString(UI_LANGUAGE, code);
        }
        editor.apply();
    }

    static String getSightengineApiUser(Context context) {
        return context
            .getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(SIGHTENGINE_API_USER, "");
    }

    static void setSightengineApiUser(Context context, String value) {
        SharedPreferences.Editor editor = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit();
        editor.putString(SIGHTENGINE_API_USER, value == null ? "" : value.trim());
        editor.apply();
    }

    static String getSightengineApiSecret(Context context) {
        return context
            .getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(SIGHTENGINE_API_SECRET, "");
    }

    static void setSightengineApiSecret(Context context, String value) {
        SharedPreferences.Editor editor = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit();
        editor.putString(SIGHTENGINE_API_SECRET, value == null ? "" : value.trim());
        editor.apply();
    }

    static boolean isClipboardAutoOpen(Context context) {
        return context
            .getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getBoolean(CLIPBOARD_AUTO_OPEN, false);
    }

    static void setClipboardAutoOpen(Context context, boolean enabled) {
        SharedPreferences.Editor editor = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit();
        editor.putBoolean(CLIPBOARD_AUTO_OPEN, enabled);
        editor.apply();
    }
}
