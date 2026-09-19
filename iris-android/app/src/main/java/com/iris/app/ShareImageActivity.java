package com.iris.app;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

public class ShareImageActivity extends Activity {
    private TextView statusText;
    private IrisScanIndicator progressBar;
    private LinearLayout bodyLayout;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        Uri imageUri = getIntent().getParcelableExtra(Intent.EXTRA_STREAM);
        if (imageUri == null) {
            renderLoading();
            showError("No shared image was provided.");
            return;
        }

        if (Settings.canDrawOverlays(this)) {
            grantUriPermission(getPackageName(), imageUri, Intent.FLAG_GRANT_READ_URI_PERMISSION);
            Intent service = new Intent(this, OverlayService.class);
            service.setAction(OverlayService.ACTION_VERIFY_IMAGE_URI);
            service.putExtra(OverlayService.EXTRA_IMAGE_URI, imageUri.toString());
            service.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            startOverlayService(service);
            finish();
            return;
        }

        renderLoading();
        IrisApiClient.verifyImageUri(this, imageUri, new IrisApiClient.Callback() {
            @Override
            public void onSuccess(String responseJson) {
                Intent intent = new Intent(ShareImageActivity.this, ResultActivity.class);
                intent.putExtra(ResultActivity.EXTRA_RESPONSE_JSON, responseJson);
                intent.putExtra(ResultActivity.EXTRA_FALLBACK_TEXT, "Image selected for OCR.");
                intent.putExtra(ResultActivity.EXTRA_INPUT_TYPE, "image");
                startActivity(intent);
                finish();
            }

            @Override
            public void onError(String message) {
                showError(message);
            }
        });
    }

    private void startOverlayService(Intent intent) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent);
        } else {
            startService(intent);
        }
    }

    private void renderLoading() {
        LinearLayout root = IrisUi.vertical(this, 18);
        root.setGravity(Gravity.CENTER);
        root.setBackgroundColor(IrisUi.BG);

        LinearLayout panel = IrisUi.card(this, 0);
        panel.addView(header(), IrisUi.matchWrap());

        bodyLayout = IrisUi.vertical(this, 20);
        bodyLayout.addView(IrisUi.eyebrow(this, "Image OCR"), IrisUi.matchWrap());
        bodyLayout.addView(imagePreview(), IrisUi.spaced(this, 8));

        progressBar = new IrisScanIndicator(this);
        bodyLayout.addView(progressBar, IrisUi.spaced(this, 18));

        TextView label = IrisUi.title(this, "Extracting image text...", 19);
        label.setGravity(Gravity.CENTER);
        bodyLayout.addView(label, IrisUi.spaced(this, 10));

        statusText = IrisUi.muted(this, "Readable text will be sent through the same IRIS verification pipeline.", 12.5f);
        statusText.setGravity(Gravity.CENTER);
        bodyLayout.addView(statusText, IrisUi.spaced(this, 6));

        panel.addView(bodyLayout, IrisUi.matchWrap());
        root.addView(panel, IrisUi.matchWrap());
        setContentView(root);
    }

    private View header() {
        LinearLayout header = IrisUi.horizontal(this, 14);
        header.setBackground(IrisUi.gradient(this, 20));

        IrisMarkView mark = new IrisMarkView(this);
        mark.setMonochrome(true);
        header.addView(mark, IrisUi.fixed(this, 32, 32));

        LinearLayout copy = IrisUi.vertical(this, 0);
        copy.addView(IrisUi.text(this, "IRIS", 20, Color.WHITE, Typeface.BOLD), IrisUi.matchWrap());
        TextView sub = IrisUi.text(this, "IMAGE VERIFICATION", 10, Color.WHITE, Typeface.BOLD);
        sub.setAlpha(0.82f);
        sub.setLetterSpacing(0.1f);
        copy.addView(sub, IrisUi.matchWrap());

        LinearLayout.LayoutParams params = IrisUi.rowWeight(1);
        params.setMargins(IrisUi.dp(this, 10), 0, 0, 0);
        header.addView(copy, params);
        return header;
    }

    private View imagePreview() {
        LinearLayout preview = IrisUi.vertical(this, 14);
        preview.setBackground(IrisUi.bordered(this, IrisUi.BLUE_BG, 14, Color.rgb(187, 218, 255)));

        TextView title = IrisUi.text(this, "Shared image received", 15, IrisUi.TEXT, Typeface.BOLD);
        preview.addView(title, IrisUi.matchWrap());
        preview.addView(IrisUi.muted(this, "IRIS will extract readable text first, then check the extracted claims.", 12.5f), IrisUi.spaced(this, 4));
        return preview;
    }

    private void showError(String message) {
        if (progressBar != null) progressBar.setVisibility(View.GONE);
        if (statusText != null) {
            statusText.setText(message == null ? "IRIS could not verify the shared image." : message);
            statusText.setTextColor(Color.rgb(153, 27, 27));
        }

        Button done = IrisUi.secondaryButton(this, "Back to IRIS");
        done.setOnClickListener(view -> finish());
        if (bodyLayout != null && done.getParent() == null) {
            bodyLayout.addView(done, IrisUi.spaced(this, 10));
        }
    }
}
