package com.iris.app;

import android.app.Activity;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

public class ResultActivity extends Activity {
    public static final String EXTRA_RESPONSE_JSON = "response_json";
    public static final String EXTRA_FALLBACK_TEXT = "fallback_text";
    public static final String EXTRA_INPUT_TYPE = "input_type";

    private IrisResultData resultData;
    private int claimIndex = 0;
    private String inputType = "text";
    // Cleared when the claim or result changes, so every verdict starts collapsed at
    // three sources; only the reader's explicit tap reveals the rest.
    private boolean sourcesExpanded = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        IrisUi.applyTheme(this);
        setTitle("IRIS Result");
        inputType = getIntent().getStringExtra(EXTRA_INPUT_TYPE);
        if (inputType == null) inputType = "text";

        resultData = IrisResultData.parse(
            getIntent().getStringExtra(EXTRA_RESPONSE_JSON),
            getIntent().getStringExtra(EXTRA_FALLBACK_TEXT),
            inputType
        );
        render();
    }

    private void render() {
        ScrollView scrollView = new ScrollView(this);
        scrollView.setFillViewport(false);

        LinearLayout root = IrisUi.vertical(this, 18);
        root.setBackgroundColor(IrisUi.BG);
        scrollView.addView(root);

        LinearLayout panel = IrisUi.card(this, 0);
        panel.addView(panelHeader(), IrisUi.matchWrap());

        LinearLayout body = IrisUi.vertical(this, 18);
        if (resultData == null || resultData.claims.isEmpty()) {
            body.addView(ResultRenderer.errorCard(this, ResultRenderer.Variant.FULL,
                "IRIS did not return a readable result."), IrisUi.matchWrap());
        } else {
            body.addView(ResultRenderer.navigator(this, ResultRenderer.Variant.FULL, claimIndex,
                resultData.claims.size(),
                () -> {
                    claimIndex = Math.max(0, claimIndex - 1);
                    sourcesExpanded = false;
                    render();
                },
                () -> {
                    claimIndex = Math.min(resultData.claims.size() - 1, claimIndex + 1);
                    sourcesExpanded = false;
                    render();
                }), IrisUi.matchWrap());
            body.addView(ResultRenderer.claimPanel(this, ResultRenderer.Variant.FULL,
                resultData.claims.get(claimIndex), "image".equals(inputType), sourcesExpanded,
                () -> {
                    sourcesExpanded = true;
                    render();
                }), IrisUi.spaced(this, 14));
        }

        if (resultData != null && !resultData.skippedSegments.isEmpty()) {
            body.addView(ResultRenderer.skippedNote(this, resultData), IrisUi.spaced(this, 14));
        }

        TextView disclaimer = IrisUi.muted(this, "IRIS is an assistant, not an authority. Always read the linked articles before sharing.", 11);
        disclaimer.setGravity(Gravity.CENTER);
        body.addView(disclaimer, IrisUi.spaced(this, 14));

        Button done = IrisUi.secondaryButton(this, "Check another claim");
        done.setOnClickListener(view -> finish());
        body.addView(done, IrisUi.spaced(this, 10));

        panel.addView(body, IrisUi.matchWrap());
        root.addView(panel, IrisUi.matchWrap());
        setContentView(scrollView);
    }

    private View panelHeader() {
        LinearLayout header = IrisUi.horizontal(this, 14);
        header.setBackground(IrisUi.gradient(this, 18));

        FrameLayout markHolder = new FrameLayout(this);
        markHolder.setBackground(IrisUi.rounded(this, Color.WHITE, 999));
        IrisMarkView mark = new IrisMarkView(this);
        FrameLayout.LayoutParams markParams = new FrameLayout.LayoutParams(
            IrisUi.dp(this, 24),
            IrisUi.dp(this, 24),
            Gravity.CENTER
        );
        markHolder.addView(mark, markParams);
        header.addView(markHolder, IrisUi.fixed(this, 36, 36));

        LinearLayout copy = IrisUi.vertical(this, 0);
        TextView name = IrisUi.text(this, "IRIS", 20, Color.WHITE, Typeface.BOLD);
        name.setIncludeFontPadding(false);
        TextView label = IrisUi.text(this, "VERIFICATION RESULT", 10, Color.WHITE, Typeface.BOLD);
        label.setAlpha(0.82f);
        label.setLetterSpacing(0.1f);
        copy.addView(name, IrisUi.matchWrap());
        copy.addView(label, IrisUi.matchWrap());

        LinearLayout.LayoutParams copyParams = IrisUi.rowWeight(1);
        copyParams.setMargins(IrisUi.dp(this, 10), 0, 0, 0);
        header.addView(copy, copyParams);

        Button close = new Button(this);
        close.setText("X");
        close.setTextColor(Color.WHITE);
        close.setTextSize(13);
        close.setAllCaps(false);
        close.setBackground(IrisUi.rounded(this, Color.argb(45, 255, 255, 255), 999));
        IrisUi.touchFeedback(close, 999);
        close.setOnClickListener(view -> finish());
        header.addView(close, IrisUi.fixed(this, 40, 40));
        return header;
    }

}
