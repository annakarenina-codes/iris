package com.iris.app;

import android.Manifest;
import android.app.Activity;
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
    private TextView statusText;
    private TextView bubbleDescription;
    private TextView bubbleStatusLabel;
    private IrisScanIndicator progressBar;
    private IrisToggleView bubbleToggle;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
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
        body.addView(androidWorkflowCard(), IrisUi.spaced(this, 14));
        body.addView(sourceTrustCard(), IrisUi.spaced(this, 14));
        if (IrisPrefs.isBackendConfigurable()) {
            body.addView(backendCard(), IrisUi.spaced(this, 14));
        }
        body.addView(manualCheckCard(), IrisUi.spaced(this, 14));
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
        TextView acronym = IrisUi.text(this, "Intelligent Real-time\nInformation Scanner", 20, Color.WHITE, Typeface.NORMAL);
        acronym.setIncludeFontPadding(false);
        acronym.setLineSpacing(0, 1.04f);
        brandCopy.addView(name, IrisUi.matchWrap());
        brandCopy.addView(acronym, IrisUi.matchWrap());

        LinearLayout.LayoutParams copyParams = IrisUi.rowWeight(1);
        copyParams.setMargins(IrisUi.dp(this, 12), 0, 0, 0);
        brandRow.addView(brandCopy, copyParams);
        header.addView(brandRow, IrisUi.matchWrap());

        TextView title = IrisUi.text(this, "Fact-check from any app", 23, Color.WHITE, Typeface.BOLD);
        title.setLineSpacing(0, 1.02f);
        header.addView(title, IrisUi.spaced(this, 22));

        TextView subtitle = IrisUi.text(
            this,
            "Enable the floating bubble, paste copied Facebook text, use Android's text menu where available, or share images to IRIS for OCR verification.",
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
        dot.setBackground(IrisUi.rounded(this, IrisUi.GREEN, 999));
        strip.addView(dot, IrisUi.fixed(this, 10, 10));

        LinearLayout copy = IrisUi.vertical(this, 0);
        copy.addView(IrisUi.text(this, "Ready to fact-check", 15, IrisUi.TEXT, Typeface.BOLD), IrisUi.matchWrap());
        statusText = IrisUi.muted(this, "IRIS only checks text or images you intentionally submit.", 12);
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
        copy.addView(IrisUi.eyebrow(this, "IRIS Bubble"), IrisUi.matchWrap());
        copy.addView(IrisUi.title(this, "Floating assistant", 20), IrisUi.spaced(this, 2));
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

        Button primary = IrisUi.primaryButton(this, "Open bubble now");
        primary.setOnClickListener(view -> enableBubble());
        card.addView(primary, IrisUi.spaced(this, 12));

        Button stop = IrisUi.secondaryButton(this, "Turn off bubble");
        stop.setOnClickListener(view -> disableBubble());
        card.addView(stop, IrisUi.spaced(this, 8));

        return card;
    }

    private View androidWorkflowCard() {
        LinearLayout card = IrisUi.card(this, 18);
        card.addView(IrisUi.eyebrow(this, "Android workflow"), IrisUi.matchWrap());
        card.addView(IrisUi.title(this, "Three user-triggered entry points", 20), IrisUi.spaced(this, 3));
        card.addView(infoRow("Facebook paste", "Long-press post text to copy it, tap the IRIS bubble, paste, then check."), IrisUi.spaced(this, 12));
        card.addView(infoRow("Text selection", "In supported apps, the Android text toolbar can show Check with IRIS."), IrisUi.spaced(this, 10));
        card.addView(infoRow("Image sharing", "Share image posts to IRIS; the app sends them to /verify-image for OCR, then shows claim results."), IrisUi.spaced(this, 10));
        return card;
    }

    private View sourceTrustCard() {
        LinearLayout card = IrisUi.card(this, 18);
        card.addView(IrisUi.eyebrow(this, "Privacy and sources"), IrisUi.matchWrap());
        card.addView(IrisUi.title(this, "User-controlled verification", 20), IrisUi.spaced(this, 3));
        card.addView(infoRow("User-triggered only", "IRIS does not monitor other apps automatically; checks begin only when you submit text or an image."), IrisUi.spaced(this, 12));
        card.addView(infoRow("Privacy first", "The clipboard is read only after you tap Paste from Clipboard inside the bubble."), IrisUi.spaced(this, 10));
        card.addView(infoRow("Approved sources", "IRIS checks VERA Files and Rappler plus ABS-CBN, GMA, Inquirer, PhilStar, Manila Bulletin, PNA, PIA, DZRH, and OneNews."), IrisUi.spaced(this, 10));
        return card;
    }

    private View backendCard() {
        LinearLayout card = IrisUi.card(this, 18);
        card.addView(IrisUi.eyebrow(this, "Backend"), IrisUi.matchWrap());
        card.addView(IrisUi.title(this, "Connection", 20), IrisUi.spaced(this, 3));
        card.addView(IrisUi.muted(this, "Use 10.0.2.2 when the Flask backend is running on the same laptop as the emulator.", 12.5f), IrisUi.spaced(this, 6));

        backendUrlInput = new EditText(this);
        backendUrlInput.setHint("http://10.0.2.2:5000");
        backendUrlInput.setSingleLine(true);
        backendUrlInput.setInputType(InputType.TYPE_TEXT_VARIATION_URI);
        backendUrlInput.setText(IrisPrefs.getBackendUrl(this));
        backendUrlInput.setTextColor(IrisUi.TEXT);
        backendUrlInput.setHintTextColor(IrisUi.TEXT_LIGHT);
        backendUrlInput.setBackground(IrisUi.bordered(this, Color.WHITE, 12, IrisUi.BORDER));
        backendUrlInput.setPadding(IrisUi.dp(this, 14), 0, IrisUi.dp(this, 14), 0);
        card.addView(backendUrlInput, IrisUi.spaced(this, 12));

        Button saveBackend = IrisUi.secondaryButton(this, "Save backend URL");
        saveBackend.setOnClickListener(view -> {
            IrisPrefs.setBackendUrl(this, backendUrlInput.getText().toString());
            setStatus("Backend URL saved.");
        });
        card.addView(saveBackend, IrisUi.spaced(this, 10));
        return card;
    }

    private View manualCheckCard() {
        LinearLayout card = IrisUi.card(this, 18);
        card.addView(IrisUi.eyebrow(this, "Check a claim"), IrisUi.matchWrap());
        card.addView(IrisUi.title(this, "Manual text and image check", 20), IrisUi.spaced(this, 3));
        card.addView(IrisUi.muted(this, "Paste a claim or choose a screenshot, and IRIS will check it against Philippine news sources.", 12.5f), IrisUi.spaced(this, 6));

        claimInput = new EditText(this);
        claimInput.setHint("Paste or type a claim to verify");
        claimInput.setMinLines(4);
        claimInput.setGravity(Gravity.TOP);
        claimInput.setTextColor(IrisUi.TEXT);
        claimInput.setHintTextColor(IrisUi.TEXT_LIGHT);
        claimInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        claimInput.setBackground(IrisUi.bordered(this, Color.WHITE, 14, IrisUi.BORDER));
        claimInput.setPadding(IrisUi.dp(this, 14), IrisUi.dp(this, 12), IrisUi.dp(this, 14), IrisUi.dp(this, 12));
        card.addView(claimInput, IrisUi.spaced(this, 12));

        Button checkText = IrisUi.primaryButton(this, "Check with IRIS");
        checkText.setOnClickListener(view -> verifyTypedText());
        card.addView(checkText, IrisUi.spaced(this, 12));

        Button pickImage = IrisUi.secondaryButton(this, "Choose image for OCR");
        pickImage.setOnClickListener(view -> openImagePicker());
        card.addView(pickImage, IrisUi.spaced(this, 10));

        progressBar = new IrisScanIndicator(this);
        progressBar.setVisibility(View.GONE);
        card.addView(progressBar, IrisUi.spaced(this, 12));
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
            setStatus("Allow IRIS to display over other apps, then return here and enable the bubble again.");
            return;
        }

        requestNotificationPermissionIfNeeded();
        IrisPrefs.setBubbleEnabled(this, true);
        Intent intent = new Intent(this, OverlayService.class);
        intent.setAction(OverlayService.ACTION_SHOW);
        startOverlayService(intent);
        setStatus("IRIS Bubble is active. Tap it to paste text, or use Android sharing/text menus.");
        updateBubbleCard();
    }

    private void disableBubble() {
        IrisPrefs.setBubbleEnabled(this, false);
        Intent intent = new Intent(this, OverlayService.class);
        intent.setAction(OverlayService.ACTION_STOP);
        startService(intent);
        setStatus("IRIS Bubble turned off.");
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
                ? "IRIS is active. Use the bubble for Facebook paste checks, selected text, or shared images."
                : "IRIS is disabled. Enable it to show the floating bubble over other apps.");
        }
        if (bubbleStatusLabel != null) {
            bubbleStatusLabel.setText(enabled ? "ON - Bubble is visible" : "OFF - Bubble is hidden");
            bubbleStatusLabel.setTextColor(enabled ? IrisUi.GREEN : IrisUi.GRAY);
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
            setStatus("Enter or select text first.");
            return;
        }

        setLoading("Scanning approved IRIS sources...");
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
            setStatus("No image was selected.");
            return;
        }

        setLoading("Extracting image text and scanning sources...");
        IrisApiClient.verifyImageUri(this, imageUri, new IrisApiClient.Callback() {
            @Override
            public void onSuccess(String responseJson) {
                showResult(responseJson, "Image selected for OCR.", "image");
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
