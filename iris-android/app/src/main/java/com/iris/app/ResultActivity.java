package com.iris.app;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Bundle;
import android.text.TextUtils;
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

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
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
            body.addView(errorCard("IRIS did not return a readable result."), IrisUi.matchWrap());
        } else {
            body.addView(navigator(), IrisUi.matchWrap());
            body.addView(claimPanel(resultData.claims.get(claimIndex)), IrisUi.spaced(this, 14));
        }

        if (resultData != null && !resultData.skippedSegments.isEmpty()) {
            body.addView(skippedNote(), IrisUi.spaced(this, 14));
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
        header.setBackground(IrisUi.gradient(this, 20));

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

    private View navigator() {
        LinearLayout row = IrisUi.horizontal(this, 0);
        row.setGravity(Gravity.CENTER);

        Button previous = roundNavButton("<");
        previous.setEnabled(claimIndex > 0);
        previous.setAlpha(claimIndex > 0 ? 1f : 0.35f);
        previous.setOnClickListener(view -> {
            claimIndex = Math.max(0, claimIndex - 1);
            render();
        });
        row.addView(previous, IrisUi.fixed(this, 46, 46));

        TextView label = IrisUi.text(this, "Claim " + (claimIndex + 1) + " of " + resultData.claims.size(), 17, IrisUi.TEXT, Typeface.BOLD);
        label.setGravity(Gravity.CENTER);
        row.addView(label, IrisUi.rowWeight(1));

        Button next = roundNavButton(">");
        next.setEnabled(claimIndex < resultData.claims.size() - 1);
        next.setAlpha(next.isEnabled() ? 1f : 0.35f);
        next.setOnClickListener(view -> {
            claimIndex = Math.min(resultData.claims.size() - 1, claimIndex + 1);
            render();
        });
        row.addView(next, IrisUi.fixed(this, 46, 46));
        return row;
    }

    private Button roundNavButton(String label) {
        Button button = new Button(this);
        button.setText(label);
        button.setTextSize(20);
        button.setTextColor(IrisUi.VIOLET);
        button.setAllCaps(false);
        button.setBackground(IrisUi.bordered(this, Color.WHITE, 999, IrisUi.BORDER));
        IrisUi.touchFeedback(button, 999);
        return button;
    }

    private View claimPanel(IrisResultData.ClaimItem claim) {
        LinearLayout wrapper = IrisUi.vertical(this, 0);
        wrapper.addView(claimBox(claim.claimText), IrisUi.matchWrap());

        if (claim.politicallySensitive) {
            wrapper.addView(politicalFlag(), IrisUi.spaced(this, 12));
        }

        wrapper.addView(verdictCard(claim), IrisUi.spaced(this, 12));
        wrapper.addView(evidenceSummary(claim), IrisUi.spaced(this, 12));
        wrapper.addView(IrisUi.eyebrow(this, "Evidence Sources"), IrisUi.spaced(this, 12));

        if (claim.sources.isEmpty()) {
            TextView empty = IrisUi.muted(this, "No valid evidence link found.", 12.5f);
            empty.setGravity(Gravity.CENTER);
            empty.setPadding(IrisUi.dp(this, 12), IrisUi.dp(this, 14), IrisUi.dp(this, 12), IrisUi.dp(this, 14));
            empty.setBackground(IrisUi.bordered(this, IrisUi.GRAY_BG, 14, IrisUi.GRAY_BORDER));
            wrapper.addView(empty, IrisUi.spaced(this, 8));
        } else {
            for (IrisResultData.SourceItem source : claim.sources) {
                wrapper.addView(sourceCard(source), IrisUi.spaced(this, 8));
            }
        }

        return wrapper;
    }

    private View claimBox(String claimText) {
        LinearLayout box = IrisUi.horizontal(this, 0);
        box.setGravity(Gravity.CENTER_VERTICAL);
        box.setBackground(IrisUi.bordered(this, IrisUi.BLUE_BG, 14, Color.rgb(187, 218, 255)));

        View accent = new View(this);
        accent.setBackgroundColor(IrisUi.BLUE_BORDER);
        box.addView(accent, new LinearLayout.LayoutParams(IrisUi.dp(this, 4), LinearLayout.LayoutParams.MATCH_PARENT));

        LinearLayout copy = IrisUi.vertical(this, 12);
        if ("image".equals(inputType)) {
            TextView label = IrisUi.eyebrow(this, "Text extracted from image");
            copy.addView(label, IrisUi.matchWrap());
        }

        TextView quote = new TextView(this);
        quote.setText(TextUtils.isEmpty(claimText) ? "No claim text returned." : claimText);
        quote.setTextColor(IrisUi.TEXT);
        quote.setTextSize(16);
        quote.setTypeface(Typeface.SERIF, Typeface.ITALIC);
        quote.setLineSpacing(0, 1.12f);
        copy.addView(quote, IrisUi.matchWrap());
        box.addView(copy, IrisUi.rowWeight(1));
        return box;
    }

    private View politicalFlag() {
        LinearLayout flag = IrisUi.horizontal(this, 12);
        flag.setBackground(IrisUi.bordered(this, IrisUi.ORANGE_BG, 14, IrisUi.ORANGE_BORDER));

        TextView icon = new TextView(this);
        icon.setText("!");
        icon.setTextSize(18);
        icon.setGravity(Gravity.CENTER);
        icon.setTextColor(IrisUi.ORANGE);
        icon.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        icon.setBackground(IrisUi.rounded(this, Color.WHITE, 999));
        flag.addView(icon, IrisUi.fixed(this, 34, 34));

        LinearLayout copy = IrisUi.vertical(this, 0);
        copy.addView(IrisUi.text(this, "Politically Sensitive", 14, IrisUi.ORANGE, Typeface.BOLD), IrisUi.matchWrap());
        copy.addView(IrisUi.text(this, "Apply extra scrutiny before sharing.", 12, IrisUi.ORANGE, Typeface.NORMAL), IrisUi.matchWrap());
        flag.addView(copy, IrisUi.rowWeight(1));
        return flag;
    }

    private View verdictCard(IrisResultData.ClaimItem claim) {
        LinearLayout card = IrisUi.horizontal(this, 14);
        int color = IrisUi.verdictColor(claim.verdict);
        card.setBackground(IrisUi.bordered(this, IrisUi.verdictBackground(claim.verdict), 14, IrisUi.verdictBorder(claim.verdict)));

        TextView icon = new TextView(this);
        icon.setText(IrisUi.verdictIcon(claim.verdict));
        icon.setTextSize(18);
        icon.setTextColor(color);
        icon.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        icon.setGravity(Gravity.CENTER);
        card.addView(icon, IrisUi.fixed(this, 42, 42));

        LinearLayout copy = IrisUi.vertical(this, 0);
        copy.addView(IrisUi.text(this, claim.verdict, 18, color, Typeface.BOLD), IrisUi.matchWrap());
        copy.addView(IrisUi.text(this, claim.message, 13.5f, color, Typeface.NORMAL), IrisUi.matchWrap());
        card.addView(copy, IrisUi.rowWeight(1));
        return card;
    }

    private View evidenceSummary(IrisResultData.ClaimItem claim) {
        LinearLayout row = IrisUi.horizontal(this, 0);

        TextView pill = new TextView(this);
        pill.setText(claim.evidenceCount + " of " + claim.evidenceTotal);
        pill.setTextColor(Color.WHITE);
        pill.setTextSize(13);
        pill.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        pill.setGravity(Gravity.CENTER);
        pill.setBackground(IrisUi.gradient(this, 999));
        row.addView(pill, IrisUi.fixed(this, 78, 34));

        TextView label = IrisUi.muted(this, claim.evidenceCount == 1 ? " evidence source used" : " evidence sources used", 13);
        row.addView(label, IrisUi.rowWeight(1));
        return row;
    }

    private View sourceCard(IrisResultData.SourceItem source) {
        LinearLayout card = IrisUi.vertical(this, 12);
        card.setBackground(IrisUi.bordered(this, Color.WHITE, 14, IrisUi.BORDER));
        card.setClickable(true);
        IrisUi.touchFeedback(card, 14);
        card.setOnClickListener(view -> {
            Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(source.url));
            startActivity(intent);
        });

        LinearLayout meta = IrisUi.horizontal(this, 0);
        meta.addView(IrisUi.text(this, source.outlet, 12, IrisUi.VIOLET, Typeface.BOLD), IrisUi.rowWeight(1));
        TextView date = IrisUi.muted(this, source.date, 11);
        date.setGravity(Gravity.END);
        meta.addView(date, IrisUi.rowWeight(1));
        card.addView(meta, IrisUi.matchWrap());

        TextView title = IrisUi.text(this, source.title, 13.5f, IrisUi.TEXT, Typeface.BOLD);
        card.addView(title, IrisUi.spaced(this, 6));

        TextView link = IrisUi.text(this, "Read full article", 12, IrisUi.VIOLET, Typeface.BOLD);
        card.addView(link, IrisUi.spaced(this, 6));
        return card;
    }

    private View skippedNote() {
        StringBuilder message = new StringBuilder("IRIS skipped ");
        for (int index = 0; index < resultData.skippedSegments.size(); index += 1) {
            IrisResultData.SkippedSegment segment = resultData.skippedSegments.get(index);
            if (index > 0) message.append(index == resultData.skippedSegments.size() - 1 ? " and " : ", ");
            message.append(segment.count).append(" ").append(segment.label);
            if (segment.count != 1) message.append("s");
        }
        message.append(" because they were not independently checkable.");

        TextView note = IrisUi.muted(this, message.toString(), 12);
        note.setGravity(Gravity.CENTER);
        note.setPadding(IrisUi.dp(this, 12), IrisUi.dp(this, 12), IrisUi.dp(this, 12), IrisUi.dp(this, 12));
        note.setBackground(IrisUi.bordered(this, IrisUi.GRAY_BG, 14, IrisUi.GRAY_BORDER));
        return note;
    }

    private View errorCard(String message) {
        TextView error = IrisUi.text(this, message, 14, Color.rgb(153, 27, 27), Typeface.BOLD);
        error.setPadding(IrisUi.dp(this, 18), IrisUi.dp(this, 16), IrisUi.dp(this, 18), IrisUi.dp(this, 16));
        error.setBackground(IrisUi.bordered(this, Color.rgb(254, 242, 242), 14, Color.rgb(252, 165, 165)));
        return error;
    }
}
