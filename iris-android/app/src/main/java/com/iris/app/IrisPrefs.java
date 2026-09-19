package com.iris.app;

import android.content.Context;
import android.content.SharedPreferences;

final class IrisPrefs {
    private static final String PREFS = "iris_settings";
    private static final String BACKEND_URL = "backend_url";
    private static final String BUBBLE_ENABLED = "bubble_enabled";
    private static final String BUBBLE_X = "bubble_x";
    private static final String BUBBLE_Y = "bubble_y";
    private static final String DEFAULT_BACKEND_URL = "http://10.0.2.2:5000";

    private IrisPrefs() {}

    static String getBackendUrl(Context context) {
        return context
            .getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(BACKEND_URL, DEFAULT_BACKEND_URL);
    }

    static void setBackendUrl(Context context, String value) {
        String cleaned = value == null ? DEFAULT_BACKEND_URL : value.trim().replaceAll("/+$", "");
        if (cleaned.isEmpty()) cleaned = DEFAULT_BACKEND_URL;

        SharedPreferences.Editor editor = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit();
        editor.putString(BACKEND_URL, cleaned);
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
}
