package com.iris.app;

import android.content.Context;
import android.content.res.ColorStateList;
import android.content.res.Configuration;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.graphics.drawable.StateListDrawable;
import android.graphics.drawable.TransitionDrawable;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

final class IrisUi {
    // Violet ramp shared with the extension: deeper root, lighter tail, so the
    // diagonal read stays legible at both ends instead of washing out.
    static int GRADIENT_START = Color.rgb(109, 40, 217);
    static int GRADIENT_MID = Color.rgb(139, 92, 246);
    static int GRADIENT_END = Color.rgb(167, 139, 250);
    static int VIOLET = Color.rgb(124, 58, 237);
    static int DEEP_VIOLET = GRADIENT_START;
    static int TEXT = Color.rgb(28, 16, 51);
    static int MUTED = Color.rgb(75, 63, 114);
    static int TEXT_LIGHT = Color.rgb(139, 127, 184);
    static int BORDER = Color.rgb(228, 220, 255);
    static int CARD = Color.WHITE;
    static int BG = Color.rgb(245, 243, 255);
    static int BLUE_BG = Color.rgb(240, 247, 255);
    static int BLUE_BORDER = Color.rgb(37, 99, 235);
    static int BLUE_OUTLINE = Color.rgb(187, 218, 255);
    static int TRACK = Color.rgb(229, 231, 235);
    static int KNOB = Color.WHITE;
    // Verdict colors are semantic, so they stay day-only: a colored badge on a dark
    // card is the point, and darkening them would drain the verdict of its meaning.
    static int GREEN = Color.rgb(6, 95, 70);
    static int GREEN_BG = Color.rgb(236, 253, 245);
    static int GREEN_BORDER = Color.rgb(110, 231, 183);
    static int AMBER = Color.rgb(120, 53, 15);
    static int AMBER_BG = Color.rgb(255, 251, 235);
    static int AMBER_BORDER = Color.rgb(252, 211, 77);
    static int RED = Color.rgb(127, 29, 29);
    static int RED_BG = Color.rgb(254, 242, 242);
    static int RED_BORDER = Color.rgb(248, 113, 113);
    static int GRAY = Color.rgb(55, 65, 81);
    static int GRAY_BG = Color.rgb(249, 250, 251);
    static int GRAY_BORDER = Color.rgb(209, 213, 219);
    static int ORANGE = Color.rgb(124, 45, 18);
    static int ORANGE_BG = Color.rgb(255, 247, 237);
    static int ORANGE_BORDER = Color.rgb(253, 186, 116);
    // Status colors are drawn straight onto themed surfaces, unlike the verdict badges
    // above that sit on their own day-only cards, so they flip with the theme.
    static int STATUS_OK = Color.rgb(6, 95, 70);
    static int STATUS_ERROR = Color.rgb(153, 27, 27);
    static int STATUS_OFF = Color.rgb(55, 65, 81);

    static final String THEME_SYSTEM = "system";
    static final String THEME_LIGHT = "light";
    static final String THEME_DARK = "dark";

    private IrisUi() {}

    /**
     * Repoints every palette token at the theme the user asked for.
     *
     * The UI is drawn from static tokens across several Activities and the overlay
     * Service, so a single mutable palette is the only shape that reaches all of them
     * without threading a theme through every constructor. The swap happens at creation
     * boundaries -- each Activity's onCreate and every overlay build -- before any view
     * is built, because backgrounds and text colors are applied while views are
     * constructed; the few views that paint themselves re-read the same tokens on draw.
     *
     * Day values are assigned first so switching back out of dark can never leave a
     * night token behind.
     */
    static void applyTheme(Context context) {
        GRADIENT_START = Color.rgb(109, 40, 217);
        GRADIENT_MID = Color.rgb(139, 92, 246);
        GRADIENT_END = Color.rgb(167, 139, 250);
        VIOLET = Color.rgb(124, 58, 237);
        DEEP_VIOLET = GRADIENT_START;
        TEXT = Color.rgb(28, 16, 51);
        MUTED = Color.rgb(75, 63, 114);
        TEXT_LIGHT = Color.rgb(139, 127, 184);
        BORDER = Color.rgb(228, 220, 255);
        CARD = Color.WHITE;
        BG = Color.rgb(245, 243, 255);
        BLUE_BG = Color.rgb(240, 247, 255);
        BLUE_BORDER = Color.rgb(37, 99, 235);
        BLUE_OUTLINE = Color.rgb(187, 218, 255);
        TRACK = Color.rgb(229, 231, 235);
        KNOB = Color.WHITE;
        GREEN = Color.rgb(6, 95, 70);
        GREEN_BG = Color.rgb(236, 253, 245);
        GREEN_BORDER = Color.rgb(110, 231, 183);
        AMBER = Color.rgb(120, 53, 15);
        AMBER_BG = Color.rgb(255, 251, 235);
        AMBER_BORDER = Color.rgb(252, 211, 77);
        RED = Color.rgb(127, 29, 29);
        RED_BG = Color.rgb(254, 242, 242);
        RED_BORDER = Color.rgb(248, 113, 113);
        GRAY = Color.rgb(55, 65, 81);
        GRAY_BG = Color.rgb(249, 250, 251);
        GRAY_BORDER = Color.rgb(209, 213, 219);
        ORANGE = Color.rgb(124, 45, 18);
        ORANGE_BG = Color.rgb(255, 247, 237);
        ORANGE_BORDER = Color.rgb(253, 186, 116);
        STATUS_OK = Color.rgb(6, 95, 70);
        STATUS_ERROR = Color.rgb(153, 27, 27);
        STATUS_OFF = Color.rgb(55, 65, 81);

        if (!isDark(context)) return;

        // Surfaces are tinted violet-black, never pure black, so the night screen keeps
        // the brand's cast and text keeps its contrast.
        BG = Color.rgb(18, 16, 26);
        CARD = Color.rgb(30, 25, 48);
        TEXT = Color.rgb(242, 238, 252);
        MUTED = Color.rgb(185, 175, 218);
        TEXT_LIGHT = Color.rgb(141, 130, 181);
        BORDER = Color.rgb(61, 51, 88);
        BLUE_BG = Color.rgb(27, 35, 51);
        BLUE_BORDER = Color.rgb(91, 130, 217);
        BLUE_OUTLINE = Color.rgb(91, 130, 217);
        TRACK = Color.rgb(51, 44, 80);
        // The thumb stays light in both themes so the OFF label keeps something to sit on.
        KNOB = Color.rgb(240, 237, 252);
        // Lightened enough to read as ink on a dark card, still clearly green/red/gray.
        STATUS_OK = Color.rgb(52, 211, 153);
        STATUS_ERROR = Color.rgb(252, 165, 165);
        STATUS_OFF = Color.rgb(156, 163, 175);
    }

    /** Resolves the stored preference, defaulting to the system night setting. */
    static boolean isDark(Context context) {
        String theme = IrisPrefs.getTheme(context);
        if (THEME_DARK.equals(theme)) return true;
        if (THEME_LIGHT.equals(theme)) return false;
        int night = context.getResources().getConfiguration().uiMode & Configuration.UI_MODE_NIGHT_MASK;
        return night == Configuration.UI_MODE_NIGHT_YES;
    }

    static int dp(Context context, float value) {
        return Math.round(value * context.getResources().getDisplayMetrics().density);
    }

    static void touchFeedback(View view, float radiusDp) {
        view.setFocusable(true);
        // Tinted from the gradient root so pressed state reads as the brand, not a gray wash.
        int tint = Color.argb(55, 109, 40, 217);
        StateListDrawable stillFeedback = new StateListDrawable();
        stillFeedback.addState(new int[] { android.R.attr.state_enabled, android.R.attr.state_pressed },
            rounded(view.getContext(), tint, radiusDp));
        stillFeedback.addState(new int[] { android.R.attr.state_enabled, android.R.attr.state_focused },
            rounded(view.getContext(), tint, radiusDp));
        stillFeedback.addState(new int[] {}, rounded(view.getContext(), Color.TRANSPARENT, radiusDp));
        RippleDrawable ripple = new RippleDrawable(ColorStateList.valueOf(tint), null,
            rounded(view.getContext(), CARD, radiusDp));
        Runnable update = () -> view.setForeground(IrisMotion.animationsEnabled() ? ripple : stillFeedback);
        IrisMotion.observe(view, update);
        update.run();
    }

    /**
     * Violet focus ring for text fields, which otherwise show no keyboard focus at all.
     *
     * The resting background is captured instead of rebuilt: a generic Drawable cannot be
     * read back for its fill color on every API level we support, and rebuilding would
     * silently replace whatever fill the call site chose. A field with no background yet
     * falls back to the input fill so the ring still has something to sit on.
     */
    static void focusRing(View view, float radiusDp) {
        Context context = view.getContext();
        Drawable existing = view.getBackground();
        // Single assignment keeps the lambda capture effectively final (Java rejects
        // the two-step null check below when the result is captured by the listener).
        Drawable resting = existing != null
            ? existing
            : bordered(context, CARD, radiusDp, BORDER);
        GradientDrawable focused = bordered(context, CARD, radiusDp, VIOLET);
        focused.setStroke(dp(context, 1.5f), VIOLET);

        view.setOnFocusChangeListener((v, hasFocus) -> {
            // Motion decides how the ring arrives, never whether it arrives: with
            // animations off IrisMotion forces the instant swap, so reduced-motion
            // users never wait on a transition (same contract as touchFeedback's
            // ripple/still pair).
            if (!IrisMotion.animationsEnabled()) {
                v.setBackground(hasFocus ? focused : resting);
                return;
            }
            // Cross-fade stays off so the resting layer keeps the field opaque while
            // only the stroke color eases over; the field must never go translucent.
            TransitionDrawable transition = new TransitionDrawable(new Drawable[] {
                hasFocus ? resting : focused,
                hasFocus ? focused : resting
            });
            v.setBackground(transition);
            transition.startTransition(160);
        });
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
        button.setElevation(dp(context, 4));
        touchFeedback(button, 14);
        return button;
    }

    static Button secondaryButton(Context context, String label) {
        Button button = new Button(context);
        button.setText(label);
        button.setTextColor(DEEP_VIOLET);
        button.setTextSize(14);
        button.setAllCaps(false);
        GradientDrawable bg = rounded(context, CARD, 14);
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
        // 18 matches the extension's panel radius, so hand-rolled cards have one
        // silhouette to align to instead of inventing their own.
        layout.setBackground(bordered(context, CARD, 18, BORDER));
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
        // A hair of tracking keeps bold headings from clotting at small sizes.
        view.setLetterSpacing(0.01f);
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
        if (normalized.equals("refuted")) return RED;
        return GRAY;
    }

    static int verdictBackground(String verdict) {
        String normalized = verdict == null ? "" : verdict.toLowerCase();
        if (normalized.equals("verified")) return GREEN_BG;
        if (normalized.equals("partially verified")) return AMBER_BG;
        if (normalized.equals("refuted")) return RED_BG;
        return GRAY_BG;
    }

    static int verdictBorder(String verdict) {
        String normalized = verdict == null ? "" : verdict.toLowerCase();
        if (normalized.equals("verified")) return GREEN_BORDER;
        if (normalized.equals("partially verified")) return AMBER_BORDER;
        if (normalized.equals("refuted")) return RED_BORDER;
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
