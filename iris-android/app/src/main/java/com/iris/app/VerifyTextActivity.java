package com.iris.app;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

public class VerifyTextActivity extends Activity {
    private TextView statusText;
    private IrisScanIndicator progressBar;
    private LinearLayout bodyLayout;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        CharSequence selected = getIntent().getCharSequenceExtra(Intent.EXTRA_PROCESS_TEXT);
        String text = selected == null ? "" : selected.toString().trim();

        if (!text.isEmpty() && Settings.canDrawOverlays(this)) {
            Intent service = new Intent(this, OverlayService.class);
            service.setAction(OverlayService.ACTION_VERIFY_TEXT);
            service.putExtra(OverlayService.EXTRA_TEXT, text);
            startOverlayService(service);
            finish();
            return;
        }

        renderLoading(text);

        if (text.isEmpty()) {
            showError("No selected text was provided.");
            return;
        }

        IrisApiClient.verifyText(this, text, new IrisApiClient.Callback() {
            @Override
            public void onSuccess(String responseJson) {
                Intent intent = new Intent(VerifyTextActivity.this, ResultActivity.class);
                intent.putExtra(ResultActivity.EXTRA_RESPONSE_JSON, responseJson);
                intent.putExtra(ResultActivity.EXTRA_FALLBACK_TEXT, text);
                intent.putExtra(ResultActivity.EXTRA_INPUT_TYPE, "text");
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

    private void renderLoading(String selectedText) {
        LinearLayout root = IrisUi.vertical(this, 18);
        root.setGravity(Gravity.CENTER);
        root.setBackgroundColor(IrisUi.BG);

        LinearLayout panel = IrisUi.card(this, 0);
        panel.addView(header(), IrisUi.matchWrap());

        bodyLayout = IrisUi.vertical(this, 20);
        bodyLayout.addView(IrisUi.eyebrow(this, "Selected text"), IrisUi.matchWrap());
        bodyLayout.addView(claimPreview(selectedText), IrisUi.spaced(this, 8));

        progressBar = new IrisScanIndicator(this);
        bodyLayout.addView(progressBar, IrisUi.spaced(this, 18));

        TextView label = IrisUi.title(this, "Scanning sources...", 19);
        label.setGravity(Gravity.CENTER);
        bodyLayout.addView(label, IrisUi.spaced(this, 10));

        statusText = IrisUi.muted(this, "Checking ABS-CBN, GMA, Inquirer, PhilStar, Manila Bulletin, PNA, PIA, and VERA Files.", 12.5f);
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
        TextView sub = IrisUi.text(this, "CHECK WITH IRIS", 10, Color.WHITE, Typeface.BOLD);
        sub.setAlpha(0.82f);
        sub.setLetterSpacing(0.1f);
        copy.addView(sub, IrisUi.matchWrap());

        LinearLayout.LayoutParams params = IrisUi.rowWeight(1);
        params.setMargins(IrisUi.dp(this, 10), 0, 0, 0);
        header.addView(copy, params);
        return header;
    }

    private View claimPreview(String selectedText) {
        TextView quote = new TextView(this);
        quote.setText(truncate(selectedText.isEmpty() ? "No selected text was provided." : selectedText));
        quote.setTextColor(IrisUi.TEXT);
        quote.setTextSize(16);
        quote.setTypeface(Typeface.SERIF, Typeface.ITALIC);
        quote.setLineSpacing(0, 1.12f);
        quote.setPadding(IrisUi.dp(this, 14), IrisUi.dp(this, 12), IrisUi.dp(this, 14), IrisUi.dp(this, 12));
        quote.setBackground(IrisUi.bordered(this, IrisUi.BLUE_BG, 14, Color.rgb(187, 218, 255)));
        return quote;
    }

    private void showError(String message) {
        if (progressBar != null) progressBar.setVisibility(View.GONE);
        if (statusText != null) {
            statusText.setText(message == null ? "IRIS could not complete the check." : message);
            statusText.setTextColor(Color.rgb(153, 27, 27));
        }

        Button done = IrisUi.secondaryButton(this, "Back to IRIS");
        done.setOnClickListener(view -> finish());
        if (bodyLayout != null && done.getParent() == null) {
            bodyLayout.addView(done, IrisUi.spaced(this, 10));
        }
    }

    private String truncate(String text) {
        if (text == null) return "";
        return text.length() > 260 ? text.substring(0, 257) + "..." : text;
    }
}
