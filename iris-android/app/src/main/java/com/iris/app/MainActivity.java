package com.iris.app;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

public class MainActivity extends Activity {
    private static final int PICK_IMAGE_REQUEST = 4001;
    private static final int NOTIFICATION_PERMISSION_REQUEST = 4002;

    private EditText backendUrlInput;
    private EditText claimInput;
    private EditText sightengineUserInput;
    private EditText sightengineSecretInput;
    private TextView statusText;
    private TextView bubbleDescription;
    private TextView bubbleStatusLabel;
    private IrisScanIndicator progressBar;
    private IrisToggleView bubbleToggle;
    private IrisToggleView clipboardToggle;

    @Override
    protected void attachBaseContext(Context newBase) {
        super.attachBaseContext(IrisLocale.wrap(newBase));
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        IrisUi.applyTheme(this);
        setTitle("IRIS");
        render();
    }

    @Override
    protected void onResume() {
        super.onResume();
        updateBubbleCard();
    }

    private void render() {
        ScrollView scrollView = new ScrollView(this);
        scrollView.setFillViewport(false);

        LinearLayout root = IrisUi.vertical(this, 0);
        root.setBackgroundColor(IrisUi.BG);
        scrollView.addView(root);

        root.addView(heroHeader(), IrisUi.matchWrap());

        LinearLayout body = IrisUi.vertical(this, 18);
        body.addView(statusStrip(), IrisUi.matchWrap());
        body.addView(bubbleControlCard(), IrisUi.spaced(this, 14));
        body.addView(clipboardCard(), IrisUi.spaced(this, 14));
        body.addView(themeCard(), IrisUi.spaced(this, 14));
        body.addView(languageCard(), IrisUi.spaced(this, 14));
        body.addView(androidWorkflowCard(), IrisUi.spaced(this, 14));
        body.addView(sourceTrustCard(), IrisUi.spaced(this, 14));
        if (IrisPrefs.isBackendConfigurable()) {
            body.addView(backendCard(), IrisUi.spaced(this, 14));
        }
        body.addView(sightengineCard(), IrisUi.spaced(this, 14));
        body.addView(manualCheckCard(), IrisUi.spaced(this, 14));
        body.addView(historyCard(), IrisUi.spaced(this, 14));
        root.addView(body, IrisUi.matchWrap());

        setContentView(scrollView);
        updateBubbleCard();
    }

    private View heroHeader() {
        LinearLayout header = IrisUi.vertical(this, 22);
        header.setBackground(IrisUi.gradient(this, 0));
        header.setMinimumHeight(IrisUi.dp(this, 184));

        LinearLayout brandRow = IrisUi.horizontal(this, 0);

        FrameLayout markHolder = new FrameLayout(this);
        markHolder.setBackground(IrisUi.rounded(this, Color.WHITE, 999));
        IrisMarkView mark = new IrisMarkView(this);
        FrameLayout.LayoutParams markParams = new FrameLayout.LayoutParams(
            IrisUi.dp(this, 34),
            IrisUi.dp(this, 34),
            Gravity.CENTER
        );
        markHolder.addView(mark, markParams);
        brandRow.addView(markHolder, IrisUi.fixed(this, 48, 48));

        LinearLayout brandCopy = IrisUi.vertical(this, 0);
        TextView name = IrisUi.text(this, "IRIS", 38, Color.WHITE, Typeface.BOLD);
        name.setIncludeFontPadding(false);
        TextView acronym = IrisUi.text(this, getString(R.string.hero_acronym), 20, Color.WHITE, Typeface.NORMAL);
        acronym.setIncludeFontPadding(false);
        acronym.setLineSpacing(0, 1.04f);
        brandCopy.addView(name, IrisUi.matchWrap());
        brandCopy.addView(acronym, IrisUi.matchWrap());

        LinearLayout.LayoutParams copyParams = IrisUi.rowWeight(1);
        copyParams.setMargins(IrisUi.dp(this, 12), 0, 0, 0);
        brandRow.addView(brandCopy, copyParams);
        header.addView(brandRow, IrisUi.matchWrap());

        TextView title = IrisUi.text(this, getString(R.string.hero_tagline), 23, Color.WHITE, Typeface.BOLD);
        title.setLineSpacing(0, 1.02f);
        header.addView(title, IrisUi.spaced(this, 22));

        TextView subtitle = IrisUi.text(
            this,
            getString(R.string.hero_subtitle),
            14,
            Color.WHITE,
            Typeface.NORMAL
        );
        subtitle.setAlpha(0.92f);
        header.addView(subtitle, IrisUi.spaced(this, 8));

        return header;
    }

    private View statusStrip() {
        LinearLayout strip = IrisUi.card(this, 15);
        strip.setOrientation(LinearLayout.HORIZONTAL);
        strip.setGravity(Gravity.CENTER_VERTICAL);

        View dot = new View(this);
        dot.setBackground(IrisUi.rounded(this, IrisUi.STATUS_OK, 999));
        strip.addView(dot, IrisUi.fixed(this, 10, 10));

        LinearLayout copy = IrisUi.vertical(this, 0);
        copy.addView(IrisUi.text(this, getString(R.string.status_ready_title), 15, IrisUi.TEXT, Typeface.BOLD), IrisUi.matchWrap());
        statusText = IrisUi.muted(this, getString(R.string.status_ready_detail), 12);
        copy.addView(statusText, IrisUi.matchWrap());

        LinearLayout.LayoutParams copyParams = IrisUi.rowWeight(1);
        copyParams.setMargins(IrisUi.dp(this, 10), 0, 0, 0);
        strip.addView(copy, copyParams);
        return strip;
    }

    private View bubbleControlCard() {
        LinearLayout card = IrisUi.card(this, 18);

        LinearLayout top = IrisUi.horizontal(this, 0);

        FrameLayout preview = new FrameLayout(this);
        preview.setBackground(IrisUi.bordered(this, Color.WHITE, 999, IrisUi.BORDER));
        preview.setElevation(IrisUi.dp(this, 6));
        IrisMarkView mark = new IrisMarkView(this);
        FrameLayout.LayoutParams markParams = new FrameLayout.LayoutParams(
            IrisUi.dp(this, 36),
            IrisUi.dp(this, 36),
            Gravity.CENTER
        );
        preview.addView(mark, markParams);
        top.addView(preview, IrisUi.fixed(this, 58, 58));

        LinearLayout copy = IrisUi.vertical(this, 0);
        copy.addView(IrisUi.eyebrow(this, getString(R.string.bubble_eyebrow)), IrisUi.matchWrap());
        copy.addView(IrisUi.title(this, getString(R.string.bubble_title), 20), IrisUi.spaced(this, 2));
        bubbleDescription = IrisUi.muted(this, "", 12.5f);
        copy.addView(bubbleDescription, IrisUi.spaced(this, 5));

        LinearLayout.LayoutParams copyParams = IrisUi.rowWeight(1);
        copyParams.setMargins(IrisUi.dp(this, 13), 0, IrisUi.dp(this, 10), 0);
        top.addView(copy, copyParams);

        bubbleToggle = new IrisToggleView(this);
        bubbleToggle.setOnClickListener(view -> toggleBubble());
        top.addView(bubbleToggle, IrisUi.fixed(this, 64, 34));
        card.addView(top, IrisUi.matchWrap());

        bubbleStatusLabel = new TextView(this);
        bubbleStatusLabel.setTextSize(13);
        bubbleStatusLabel.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        bubbleStatusLabel.setGravity(Gravity.CENTER);
        bubbleStatusLabel.setPadding(IrisUi.dp(this, 12), IrisUi.dp(this, 10), IrisUi.dp(this, 12), IrisUi.dp(this, 10));
        card.addView(bubbleStatusLabel, IrisUi.spaced(this, 14));

        Button primary = IrisUi.primaryButton(this, getString(R.string.bubble_open));
        primary.setOnClickListener(view -> enableBubble());
        card.addView(primary, IrisUi.spaced(this, 12));

        Button stop = IrisUi.secondaryButton(this, getString(R.string.bubble_stop));
        stop.setOnClickListener(view -> disableBubble());
        card.addView(stop, IrisUi.spaced(this, 8));

        return card;
    }

    /**
     * The clipboard auto-open choice, next to the bubble card it affects. Off by default:
     * the switch is the privacy boundary — only turning it on lets the panel read the
     * clipboard when it opens, which is why the copy stays tap-Paste-only otherwise.
     */
    private View clipboardCard() {
        LinearLayout card = IrisUi.card(this, 18);
        card.addView(IrisUi.eyebrow(this, getString(R.string.clipboard_eyebrow)), IrisUi.matchWrap());
        card.addView(IrisUi.title(this, getString(R.string.clipboard_title), 20), IrisUi.spaced(this, 3));
        card.addView(IrisUi.muted(this, getString(R.string.clipboard_desc), 12.5f), IrisUi.spaced(this, 6));

        LinearLayout row = IrisUi.horizontal(this, 0);
        row.setGravity(Gravity.CENTER_VERTICAL);

        TextView label = IrisUi.text(
            this,
            getString(R.string.clipboard_toggle_label),
            13.5f,
            IrisUi.TEXT,
            Typeface.BOLD
        );
        LinearLayout.LayoutParams labelParams = IrisUi.rowWeight(1);
        labelParams.rightMargin = IrisUi.dp(this, 12);
        row.addView(label, labelParams);

        clipboardToggle = new IrisToggleView(this);
        clipboardToggle.setContentDescription(getString(R.string.clipboard_toggle_label));
        clipboardToggle.setChecked(IrisPrefs.isClipboardAutoOpen(this));
        clipboardToggle.setOnClickListener(view -> toggleClipboardAutoOpen());
        row.addView(clipboardToggle, IrisUi.fixed(this, 64, 34));
        card.addView(row, IrisUi.spaced(this, 12));
        return card;
    }

    private void toggleClipboardAutoOpen() {
        boolean next = !IrisPrefs.isClipboardAutoOpen(this);
        IrisPrefs.setClipboardAutoOpen(this, next);
        clipboardToggle.setChecked(next);
    }

    private View themeCard() {
        LinearLayout card = IrisUi.card(this, 18);
        card.addView(IrisUi.eyebrow(this, getString(R.string.appearance_eyebrow)), IrisUi.matchWrap());
        card.addView(IrisUi.title(this, getString(R.string.theme_title), 20), IrisUi.spaced(this, 3));
        card.addView(
            IrisUi.muted(this, getString(R.string.theme_desc), 12.5f),
            IrisUi.spaced(this, 6)
        );

        String current = IrisPrefs.getTheme(this);
        LinearLayout row = IrisUi.horizontal(this, 0);
        row.addView(themeOption(getString(R.string.theme_system), IrisUi.THEME_SYSTEM, current), IrisUi.rowWeight(1));
        LinearLayout.LayoutParams lightParams = IrisUi.rowWeight(1);
        lightParams.leftMargin = IrisUi.dp(this, 8);
        row.addView(themeOption(getString(R.string.theme_light), IrisUi.THEME_LIGHT, current), lightParams);
        LinearLayout.LayoutParams darkParams = IrisUi.rowWeight(1);
        darkParams.leftMargin = IrisUi.dp(this, 8);
        row.addView(themeOption(getString(R.string.theme_dark), IrisUi.THEME_DARK, current), darkParams);
        card.addView(row, IrisUi.spaced(this, 12));
        return card;
    }

    private Button themeOption(String label, String value, String current) {
        boolean active = value.equals(current);
        Button button = new Button(this);
        button.setText(label);
        button.setTextSize(13);
        button.setAllCaps(false);
        button.setTypeface(Typeface.DEFAULT, active ? Typeface.BOLD : Typeface.NORMAL);
        // Selected means violet on an inset surface, so the choice reads without
        // depending on color alone.
        button.setTextColor(active ? IrisUi.VIOLET : IrisUi.TEXT);
        button.setBackground(IrisUi.bordered(
            this,
            active ? IrisUi.BG : IrisUi.CARD,
            12,
            active ? IrisUi.VIOLET : IrisUi.BORDER
        ));
        button.setMinHeight(IrisUi.dp(this, 42));
        IrisUi.touchFeedback(button, 12);
        button.setOnClickListener(view -> selectTheme(value));
        return button;
    }

    private void selectTheme(String value) {
        if (value.equals(IrisPrefs.getTheme(this))) return;
        IrisPrefs.setTheme(this, value);
        IrisUi.applyTheme(this);
        // The overlay shares this process and rebuilds its panel from the palette on the
        // next open, so an ACTION_SHOW is only a repaint nudge for a visible bubble.
        // Restarting the service instead would run onDestroy, which marks the bubble
        // disabled and could strand it.
        if (IrisPrefs.isBubbleEnabled(this)) {
            Intent intent = new Intent(this, OverlayService.class);
            intent.setAction(OverlayService.ACTION_SHOW);
            startOverlayService(intent);
        }
        recreate();
    }

    private View languageCard() {
        LinearLayout card = IrisUi.card(this, 18);
        card.addView(IrisUi.eyebrow(this, getString(R.string.language_eyebrow)), IrisUi.matchWrap());
        card.addView(IrisUi.title(this, getString(R.string.language_title), 20), IrisUi.spaced(this, 3));
        card.addView(IrisUi.muted(this, getString(R.string.language_desc), 12.5f), IrisUi.spaced(this, 6));

        final String[] codes = new String[IrisLocale.LANGUAGES.length];
        final String[] labels = new String[IrisLocale.LANGUAGES.length];
        String current = IrisLocale.get(this);
        int selectedIndex = 0;
        for (int i = 0; i < IrisLocale.LANGUAGES.length; i++) {
            codes[i] = IrisLocale.LANGUAGES[i][0];
            labels[i] = IrisLocale.LANGUAGES[i][1];
            if (codes[i].equals(current)) selectedIndex = i;
        }
        final int checked = selectedIndex;

        Button picker = IrisUi.secondaryButton(this, IrisLocale.label(current));
        picker.setOnClickListener(view -> new AlertDialog.Builder(this)
            .setTitle(getString(R.string.language_title))
            .setSingleChoiceItems(labels, checked, (dialog, which) -> {
                dialog.dismiss();
                selectLanguage(codes[which]);
            })
            .show());
        card.addView(picker, IrisUi.spaced(this, 12));
        return card;
    }

    /**
     * Same choreography as selectTheme: the overlay shares this process, so an
     * ACTION_SHOW repaint nudge picks the new strings up through IrisLocale.apply
     * without a restart that could strand the bubble; recreate() re-attaches this
     * Activity's context in the new language.
     */
    private void selectLanguage(String code) {
        if (code.equals(IrisLocale.get(this))) return;
        IrisPrefs.setUiLanguage(this, code);
        if (IrisPrefs.isBubbleEnabled(this)) {
            Intent intent = new Intent(this, OverlayService.class);
            intent.setAction(OverlayService.ACTION_SHOW);
            startOverlayService(intent);
        }
        recreate();
    }

    private View androidWorkflowCard() {
        LinearLayout card = IrisUi.card(this, 18);
        card.addView(IrisUi.eyebrow(this, getString(R.string.workflow_eyebrow)), IrisUi.matchWrap());
        card.addView(IrisUi.title(this, getString(R.string.workflow_title), 20), IrisUi.spaced(this, 3));
        card.addView(infoRow(getString(R.string.workflow_paste_title), getString(R.string.workflow_paste_detail)), IrisUi.spaced(this, 12));
        card.addView(infoRow(getString(R.string.workflow_select_title), getString(R.string.workflow_select_detail)), IrisUi.spaced(this, 10));
        card.addView(infoRow(getString(R.string.workflow_share_title), getString(R.string.workflow_share_detail)), IrisUi.spaced(this, 10));
        return card;
    }

    private View sourceTrustCard() {
        LinearLayout card = IrisUi.card(this, 18);
        card.addView(IrisUi.eyebrow(this, getString(R.string.privacy_eyebrow)), IrisUi.matchWrap());
        card.addView(IrisUi.title(this, getString(R.string.privacy_title), 20), IrisUi.spaced(this, 3));
        card.addView(infoRow(getString(R.string.privacy_trigger_title), getString(R.string.privacy_trigger_detail)), IrisUi.spaced(this, 12));
        card.addView(infoRow(getString(R.string.privacy_clipboard_title), getString(R.string.privacy_clipboard_detail)), IrisUi.spaced(this, 10));
        card.addView(infoRow(getString(R.string.privacy_sources_title), getString(R.string.privacy_sources_detail)), IrisUi.spaced(this, 10));
        return card;
    }

    private View backendCard() {
        LinearLayout card = IrisUi.card(this, 18);
        card.addView(IrisUi.eyebrow(this, getString(R.string.backend_eyebrow)), IrisUi.matchWrap());
        card.addView(IrisUi.title(this, getString(R.string.backend_title), 20), IrisUi.spaced(this, 3));
        card.addView(IrisUi.muted(this, getString(R.string.backend_desc), 12.5f), IrisUi.spaced(this, 6));

        backendUrlInput = new EditText(this);
        backendUrlInput.setHint("http://10.0.2.2:5000");
        backendUrlInput.setSingleLine(true);
        backendUrlInput.setInputType(InputType.TYPE_TEXT_VARIATION_URI);
        backendUrlInput.setText(IrisPrefs.getBackendUrl(this));
        backendUrlInput.setTextColor(IrisUi.TEXT);
        backendUrlInput.setHintTextColor(IrisUi.TEXT_LIGHT);
        backendUrlInput.setBackground(IrisUi.bordered(this, IrisUi.CARD, 12, IrisUi.BORDER));
        backendUrlInput.setPadding(IrisUi.dp(this, 14), 0, IrisUi.dp(this, 14), 0);
        IrisUi.focusRing(backendUrlInput, 12);
        card.addView(backendUrlInput, IrisUi.spaced(this, 12));

        Button saveBackend = IrisUi.secondaryButton(this, getString(R.string.backend_save));
        saveBackend.setOnClickListener(view -> {
            IrisPrefs.setBackendUrl(this, backendUrlInput.getText().toString());
            setStatus(getString(R.string.status_backend_saved));
        });
        card.addView(saveBackend, IrisUi.spaced(this, 10));
        return card;
    }

    /**
     * Bring-your-own-key for the AI-image detector, mirroring the extension's settings:
     * the credentials are typed here, stored on this device, and never ship in the APK.
     * Without them, image checks still run — they just report the honest
     * "Not assessed" badge instead of a verdict.
     */
    private View sightengineCard() {
        LinearLayout card = IrisUi.card(this, 18);
        card.addView(IrisUi.eyebrow(this, getString(R.string.sightengine_eyebrow)), IrisUi.matchWrap());
        card.addView(IrisUi.title(this, getString(R.string.sightengine_title), 20), IrisUi.spaced(this, 3));
        card.addView(IrisUi.muted(this, getString(R.string.sightengine_desc), 12.5f), IrisUi.spaced(this, 6));

        sightengineUserInput = new EditText(this);
        sightengineUserInput.setHint(getString(R.string.sightengine_user_hint));
        sightengineUserInput.setSingleLine(true);
        sightengineUserInput.setText(IrisPrefs.getSightengineApiUser(this));
        sightengineUserInput.setTextColor(IrisUi.TEXT);
        sightengineUserInput.setHintTextColor(IrisUi.TEXT_LIGHT);
        sightengineUserInput.setBackground(IrisUi.bordered(this, IrisUi.CARD, 12, IrisUi.BORDER));
        sightengineUserInput.setPadding(IrisUi.dp(this, 14), 0, IrisUi.dp(this, 14), 0);
        IrisUi.focusRing(sightengineUserInput, 12);
        card.addView(sightengineUserInput, IrisUi.spaced(this, 12));

        sightengineSecretInput = new EditText(this);
        sightengineSecretInput.setHint(getString(R.string.sightengine_secret_hint));
        sightengineSecretInput.setSingleLine(true);
        sightengineSecretInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        sightengineSecretInput.setText(IrisPrefs.getSightengineApiSecret(this));
        sightengineSecretInput.setTextColor(IrisUi.TEXT);
        sightengineSecretInput.setHintTextColor(IrisUi.TEXT_LIGHT);
        sightengineSecretInput.setBackground(IrisUi.bordered(this, IrisUi.CARD, 12, IrisUi.BORDER));
        sightengineSecretInput.setPadding(IrisUi.dp(this, 14), 0, IrisUi.dp(this, 14), 0);
        IrisUi.focusRing(sightengineSecretInput, 12);
        card.addView(sightengineSecretInput, IrisUi.spaced(this, 12));

        Button saveKeys = IrisUi.secondaryButton(this, getString(R.string.sightengine_save));
        saveKeys.setOnClickListener(view -> {
            IrisPrefs.setSightengineApiUser(this, sightengineUserInput.getText().toString());
            IrisPrefs.setSightengineApiSecret(this, sightengineSecretInput.getText().toString());
            setStatus(getString(R.string.status_sightengine_saved));
        });
        card.addView(saveKeys, IrisUi.spaced(this, 10));
        return card;
    }

    private View manualCheckCard() {
        LinearLayout card = IrisUi.card(this, 18);
        card.addView(IrisUi.eyebrow(this, getString(R.string.manual_eyebrow)), IrisUi.matchWrap());
        card.addView(IrisUi.title(this, getString(R.string.manual_title), 20), IrisUi.spaced(this, 3));
        card.addView(IrisUi.muted(this, getString(R.string.manual_desc), 12.5f), IrisUi.spaced(this, 6));

        claimInput = new EditText(this);
        claimInput.setHint(getString(R.string.manual_input_hint));
        claimInput.setMinLines(4);
        claimInput.setGravity(Gravity.TOP);
        claimInput.setTextColor(IrisUi.TEXT);
        claimInput.setHintTextColor(IrisUi.TEXT_LIGHT);
        claimInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        claimInput.setBackground(IrisUi.bordered(this, IrisUi.CARD, 14, IrisUi.BORDER));
        claimInput.setPadding(IrisUi.dp(this, 14), IrisUi.dp(this, 12), IrisUi.dp(this, 14), IrisUi.dp(this, 12));
        IrisUi.focusRing(claimInput, 14);
        card.addView(claimInput, IrisUi.spaced(this, 12));

        Button checkText = IrisUi.primaryButton(this, getString(R.string.process_text_label));
        checkText.setOnClickListener(view -> verifyTypedText());
        card.addView(checkText, IrisUi.spaced(this, 12));

        Button pickImage = IrisUi.secondaryButton(this, getString(R.string.manual_pick_image));
        pickImage.setOnClickListener(view -> openImagePicker());
        card.addView(pickImage, IrisUi.spaced(this, 10));

        progressBar = new IrisScanIndicator(this);
        progressBar.setVisibility(View.GONE);
        card.addView(progressBar, IrisUi.spaced(this, 12));
        return card;
    }

    private View historyCard() {
        LinearLayout card = IrisUi.card(this, 18);
        card.addView(IrisUi.eyebrow(this, getString(R.string.history_eyebrow)), IrisUi.matchWrap());
        card.addView(IrisUi.title(this, getString(R.string.history_title), 20), IrisUi.spaced(this, 3));
        card.addView(IrisUi.muted(this, getString(R.string.history_desc), 12.5f), IrisUi.spaced(this, 6));

        Button openHistory = IrisUi.secondaryButton(this, getString(R.string.history_open));
        openHistory.setOnClickListener(view -> startActivity(new Intent(this, HistoryActivity.class)));
        card.addView(openHistory, IrisUi.spaced(this, 12));
        return card;
    }

    private View infoRow(String title, String detail) {
        LinearLayout row = IrisUi.horizontal(this, 0);

        TextView badge = new TextView(this);
        badge.setText("i");
        badge.setTextSize(15);
        badge.setGravity(Gravity.CENTER);
        badge.setTextColor(IrisUi.VIOLET);
        badge.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        badge.setBackground(IrisUi.rounded(this, IrisUi.BG, 999));
        row.addView(badge, IrisUi.fixed(this, 34, 34));

        LinearLayout copy = IrisUi.vertical(this, 0);
        copy.addView(IrisUi.text(this, title, 13.5f, IrisUi.TEXT, Typeface.BOLD), IrisUi.matchWrap());
        copy.addView(IrisUi.muted(this, detail, 12), IrisUi.matchWrap());

        LinearLayout.LayoutParams copyParams = IrisUi.rowWeight(1);
        copyParams.setMargins(IrisUi.dp(this, 10), 0, 0, 0);
        row.addView(copy, copyParams);
        return row;
    }

    private void toggleBubble() {
        if (IrisPrefs.isBubbleEnabled(this)) {
            disableBubble();
        } else {
            enableBubble();
        }
    }

    private void enableBubble() {
        if (!Settings.canDrawOverlays(this)) {
            IrisPrefs.setBubbleEnabled(this, false);
            updateBubbleCard();
            Intent intent = new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION);
            intent.setData(Uri.parse("package:" + getPackageName()));
            startActivity(intent);
        setStatus(getString(R.string.status_overlay_permission));
        return;
    }

    requestNotificationPermissionIfNeeded();
        IrisPrefs.setBubbleEnabled(this, true);
        Intent intent = new Intent(this, OverlayService.class);
        intent.setAction(OverlayService.ACTION_SHOW);
        startOverlayService(intent);
        setStatus(getString(R.string.status_bubble_active));
        updateBubbleCard();
    }

    private void disableBubble() {
        IrisPrefs.setBubbleEnabled(this, false);
        Intent intent = new Intent(this, OverlayService.class);
        intent.setAction(OverlayService.ACTION_STOP);
        startService(intent);
        setStatus(getString(R.string.status_bubble_off));
        updateBubbleCard();
    }

    private void startOverlayService(Intent intent) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && !OverlayService.ACTION_STOP.equals(intent.getAction())) {
            startForegroundService(intent);
        } else {
            startService(intent);
        }
    }

    private void requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return;
        if (checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED) return;
        requestPermissions(new String[] { Manifest.permission.POST_NOTIFICATIONS }, NOTIFICATION_PERMISSION_REQUEST);
    }

    private void updateBubbleCard() {
        boolean enabled = IrisPrefs.isBubbleEnabled(this);
        if (bubbleToggle != null) {
            bubbleToggle.setChecked(enabled);
        }
        if (bubbleDescription != null) {
            bubbleDescription.setText(enabled
                ? getString(R.string.bubble_desc_on)
                : getString(R.string.bubble_desc_off));
        }
        if (bubbleStatusLabel != null) {
            bubbleStatusLabel.setText(enabled
                ? getString(R.string.bubble_state_on)
                : getString(R.string.bubble_state_off));
            bubbleStatusLabel.setTextColor(enabled ? IrisUi.STATUS_OK : IrisUi.STATUS_OFF);
            bubbleStatusLabel.setBackground(IrisUi.bordered(
                this,
                enabled ? IrisUi.GREEN_BG : IrisUi.GRAY_BG,
                14,
                enabled ? IrisUi.GREEN_BORDER : IrisUi.GRAY_BORDER
            ));
        }
    }

    private void verifyTypedText() {
        String text = claimInput.getText().toString().trim();
        if (text.isEmpty()) {
            setStatus(getString(R.string.status_empty_text));
            return;
        }

        setLoading(getString(R.string.status_scanning));
        IrisApiClient.verifyText(this, text, new IrisApiClient.Callback() {
            @Override
            public void onSuccess(String responseJson) {
                showResult(responseJson, text, "text");
            }

            @Override
            public void onError(String message) {
                stopLoading();
                setStatus(message);
            }
        });
    }

    private void openImagePicker() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("image/*");
        startActivityForResult(intent, PICK_IMAGE_REQUEST);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != PICK_IMAGE_REQUEST || resultCode != RESULT_OK || data == null) return;

        Uri imageUri = data.getData();
        if (imageUri == null) {
            setStatus(getString(R.string.status_no_image));
            return;
        }

        setLoading(getString(R.string.status_extracting));
        IrisApiClient.verifyImageUri(this, imageUri, new IrisApiClient.Callback() {
            @Override
            public void onSuccess(String responseJson) {
                showResult(responseJson, getString(R.string.status_image_ocr), "image");
            }

            @Override
            public void onError(String message) {
                stopLoading();
                setStatus(message);
            }
        });
    }

    private void showResult(String responseJson, String fallbackText, String inputType) {
        stopLoading();
        // Manual checks never pass through OverlayService, so history is recorded here too.
        HistoryStore.record(this, responseJson, fallbackText, inputType);
        Intent intent = new Intent(this, ResultActivity.class);
        intent.putExtra(ResultActivity.EXTRA_RESPONSE_JSON, responseJson);
        intent.putExtra(ResultActivity.EXTRA_FALLBACK_TEXT, fallbackText);
        intent.putExtra(ResultActivity.EXTRA_INPUT_TYPE, inputType);
        startActivity(intent);
    }

    private void setLoading(String message) {
        progressBar.setVisibility(View.VISIBLE);
        setStatus(message);
    }

    private void stopLoading() {
        progressBar.setVisibility(View.GONE);
    }

    private void setStatus(String message) {
        if (statusText != null) {
            statusText.setText(message == null ? "" : message);
        }
    }
}
