package com.iris.app;

import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.graphics.drawable.StateListDrawable;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

final class IrisUi {
    static final int GRADIENT_START = Color.rgb(91, 33, 182);
    static final int GRADIENT_MID = Color.rgb(139, 92, 246);
    static final int GRADIENT_END = Color.rgb(196, 181, 253);
    static final int VIOLET = Color.rgb(124, 58, 237);
    static final int DEEP_VIOLET = GRADIENT_START;
    static final int TEXT = Color.rgb(28, 16, 51);
    static final int MUTED = Color.rgb(75, 63, 114);
    static final int TEXT_LIGHT = Color.rgb(139, 127, 184);
    static final int BORDER = Color.rgb(228, 220, 255);
    static final int CARD = Color.WHITE;
    static final int BG = Color.rgb(245, 243, 255);
    static final int BLUE_BG = Color.rgb(240, 247, 255);
    static final int BLUE_BORDER = Color.rgb(37, 99, 235);
    static final int GREEN = Color.rgb(6, 95, 70);
    static final int GREEN_BG = Color.rgb(236, 253, 245);
    static final int GREEN_BORDER = Color.rgb(110, 231, 183);
    static final int AMBER = Color.rgb(120, 53, 15);
    static final int AMBER_BG = Color.rgb(255, 251, 235);
    static final int AMBER_BORDER = Color.rgb(252, 211, 77);
    static final int GRAY = Color.rgb(55, 65, 81);
    static final int GRAY_BG = Color.rgb(249, 250, 251);
    static final int GRAY_BORDER = Color.rgb(209, 213, 219);
    static final int ORANGE = Color.rgb(124, 45, 18);
    static final int ORANGE_BG = Color.rgb(255, 247, 237);
    static final int ORANGE_BORDER = Color.rgb(253, 186, 116);

    private IrisUi() {}

    static int dp(Context context, float value) {
        return Math.round(value * context.getResources().getDisplayMetrics().density);
    }

    static void touchFeedback(View view, float radiusDp) {
        view.setFocusable(true);
        int tint = Color.argb(55, 124, 58, 237);
        StateListDrawable stillFeedback = new StateListDrawable();
        stillFeedback.addState(new int[] { android.R.attr.state_enabled, android.R.attr.state_pressed },
            rounded(view.getContext(), tint, radiusDp));
        stillFeedback.addState(new int[] { android.R.attr.state_enabled, android.R.attr.state_focused },
            rounded(view.getContext(), tint, radiusDp));
        stillFeedback.addState(new int[] {}, rounded(view.getContext(), Color.TRANSPARENT, radiusDp));
        RippleDrawable ripple = new RippleDrawable(ColorStateList.valueOf(tint), null,
            rounded(view.getContext(), Color.WHITE, radiusDp));
        Runnable update = () -> view.setForeground(IrisMotion.animationsEnabled() ? ripple : stillFeedback);
        IrisMotion.observe(view, update);
        update.run();
    }

    static TextView text(Context context, String value, float sp, int color, int style) {
        TextView view = new TextView(context);
        view.setText(value);
        view.setTextSize(sp);
        view.setTextColor(color);
        view.setTypeface(Typeface.DEFAULT, style);
        view.setLineSpacing(0, 1.12f);
        view.setIncludeFontPadding(true);
        return view;
    }

    static Button primaryButton(Context context, String label) {
        Button button = new Button(context);
        button.setText(label);
        button.setTextColor(Color.WHITE);
        button.setTextSize(14);
        button.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        button.setAllCaps(false);
        button.setBackground(gradient(context, 14));
        button.setMinHeight(dp(context, 48));
        button.setPadding(dp(context, 18), dp(context, 10), dp(context, 18), dp(context, 10));
        button.setElevation(dp(context, 3));
        touchFeedback(button, 14);
        return button;
    }

    static Button secondaryButton(Context context, String label) {
        Button button = new Button(context);
        button.setText(label);
        button.setTextColor(DEEP_VIOLET);
        button.setTextSize(14);
        button.setAllCaps(false);
        GradientDrawable bg = rounded(context, Color.WHITE, 14);
        bg.setStroke(dp(context, 1.5f), BORDER);
        button.setBackground(bg);
        button.setMinHeight(dp(context, 48));
        touchFeedback(button, 14);
        return button;
    }

    static Button ghostButton(Context context, String label) {
        Button button = secondaryButton(context, label);
        GradientDrawable bg = rounded(context, BG, 14);
        bg.setStroke(dp(context, 1.5f), BORDER);
        button.setBackground(bg);
        return button;
    }

    static GradientDrawable rounded(Context context, int color, float radiusDp) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(color);
        drawable.setCornerRadius(dp(context, radiusDp));
        return drawable;
    }

    static GradientDrawable rounded(int color, float radius) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(color);
        drawable.setCornerRadius(radius);
        return drawable;
    }

    static GradientDrawable bordered(Context context, int color, float radiusDp, int borderColor) {
        GradientDrawable drawable = rounded(context, color, radiusDp);
        drawable.setStroke(dp(context, 1.25f), borderColor);
        return drawable;
    }

    static GradientDrawable gradient(Context context, float radiusDp) {
        GradientDrawable drawable = new GradientDrawable(
            GradientDrawable.Orientation.TL_BR,
            new int[] { GRADIENT_START, GRADIENT_MID, GRADIENT_END }
        );
        drawable.setCornerRadius(dp(context, radiusDp));
        return drawable;
    }

    static LinearLayout vertical(Context context, int padding) {
        LinearLayout layout = new LinearLayout(context);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(dp(context, padding), dp(context, padding), dp(context, padding), dp(context, padding));
        return layout;
    }

    static LinearLayout horizontal(Context context, int padding) {
        LinearLayout layout = new LinearLayout(context);
        layout.setOrientation(LinearLayout.HORIZONTAL);
        layout.setGravity(Gravity.CENTER_VERTICAL);
        layout.setPadding(dp(context, padding), dp(context, padding), dp(context, padding), dp(context, padding));
        return layout;
    }

    static LinearLayout card(Context context, int padding) {
        LinearLayout layout = vertical(context, padding);
        layout.setBackground(bordered(context, CARD, 20, BORDER));
        layout.setElevation(dp(context, 3));
        return layout;
    }

    static TextView eyebrow(Context context, String value) {
        TextView view = text(context, value, 11, VIOLET, Typeface.BOLD);
        view.setAllCaps(true);
        view.setLetterSpacing(0.08f);
        return view;
    }

    static TextView title(Context context, String value, float size) {
        TextView view = text(context, value, size, TEXT, Typeface.BOLD);
        view.setLineSpacing(0, 1.03f);
        return view;
    }

    static TextView muted(Context context, String value, float size) {
        return text(context, value, size, MUTED, Typeface.NORMAL);
    }

    static LinearLayout.LayoutParams matchWrap() {
        return new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        );
    }

    static LinearLayout.LayoutParams fixed(Context context, float widthDp, float heightDp) {
        return new LinearLayout.LayoutParams(dp(context, widthDp), dp(context, heightDp));
    }

    static LinearLayout.LayoutParams spaced() {
        LinearLayout.LayoutParams params = matchWrap();
        params.setMargins(0, 12, 0, 0);
        return params;
    }

    static LinearLayout.LayoutParams spaced(Context context, float topDp) {
        LinearLayout.LayoutParams params = matchWrap();
        params.setMargins(0, dp(context, topDp), 0, 0);
        return params;
    }

    static LinearLayout.LayoutParams rowWeight(float weight) {
        return new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, weight);
    }

    static void center(View view) {
        if (view instanceof TextView) {
            ((TextView) view).setGravity(Gravity.CENTER);
        }
    }

    static int verdictColor(String verdict) {
        String normalized = verdict == null ? "" : verdict.toLowerCase();
        if (normalized.equals("verified")) return GREEN;
        if (normalized.equals("partially verified")) return AMBER;
        return GRAY;
    }

    static int verdictBackground(String verdict) {
        String normalized = verdict == null ? "" : verdict.toLowerCase();
        if (normalized.equals("verified")) return GREEN_BG;
        if (normalized.equals("partially verified")) return AMBER_BG;
        return GRAY_BG;
    }

    static int verdictBorder(String verdict) {
        String normalized = verdict == null ? "" : verdict.toLowerCase();
        if (normalized.equals("verified")) return GREEN_BORDER;
        if (normalized.equals("partially verified")) return AMBER_BORDER;
        return GRAY_BORDER;
    }

    static String verdictIcon(String verdict) {
        String normalized = verdict == null ? "" : verdict.toLowerCase();
        if (normalized.equals("verified")) return "OK";
        if (normalized.equals("partially verified")) return "!";
        if (normalized.contains("failed") || normalized.contains("error")) return "!";
        return "?";
    }
}
