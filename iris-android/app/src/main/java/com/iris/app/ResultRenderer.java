package com.iris.app;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.text.TextUtils;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * Shared rendering for a verification result, used by the full-screen ResultActivity
 * and by the overlay panel in OverlayService so both surfaces stay in lockstep.
 *
 * FULL renders at the larger full-screen sizes; COMPACT renders the same layout at
 * the smaller sizes the overlay panel has always used. State that belongs to the
 * caller (claim index, expanded sources) arrives as plain values and callbacks, so
 * this class never holds a reference to a screen or a service.
 */
final class ResultRenderer {
    enum Variant { FULL, COMPACT }

    private ResultRenderer() {}

    static View navigator(Context context, Variant variant, int claimIndex, int total,
                          Runnable onPrevious, Runnable onNext) {
        boolean compact = variant == Variant.COMPACT;
        int buttonSize = compact ? 44 : 46;
        float buttonTextSize = compact ? 19f : 20f;
        float labelSize = compact ? 16f : 17f;

        LinearLayout row = IrisUi.horizontal(context, 0);
        row.setGravity(Gravity.CENTER);

        Button previous = roundNavButton(context, "<", buttonTextSize);
        previous.setEnabled(claimIndex > 0);
        previous.setAlpha(claimIndex > 0 ? 1f : 0.35f);
        previous.setOnClickListener(view -> onPrevious.run());
        row.addView(previous, IrisUi.fixed(context, buttonSize, buttonSize));

        TextView label = IrisUi.text(context, "Claim " + (claimIndex + 1) + " of " + total,
            labelSize, IrisUi.TEXT, Typeface.BOLD);
        label.setGravity(Gravity.CENTER);
        row.addView(label, IrisUi.rowWeight(1));

        Button next = roundNavButton(context, ">", buttonTextSize);
        next.setEnabled(claimIndex < total - 1);
        next.setAlpha(next.isEnabled() ? 1f : 0.35f);
        next.setOnClickListener(view -> onNext.run());
        row.addView(next, IrisUi.fixed(context, buttonSize, buttonSize));
        return row;
    }

    static View claimPanel(Context context, Variant variant, IrisResultData.ClaimItem claim,
                           boolean imageInput, boolean sourcesExpanded, Runnable onShowMore) {
        boolean compact = variant == Variant.COMPACT;
        int sectionGap = compact ? 10 : 12;
        int itemGap = 8;

        LinearLayout wrapper = IrisUi.vertical(context, 0);
        wrapper.addView(claimBox(context, variant, claim.claimText, imageInput), IrisUi.matchWrap());

        if (claim.politicallySensitive) {
            wrapper.addView(politicalFlag(context, variant), IrisUi.spaced(context, sectionGap));
        }

        wrapper.addView(verdictCard(context, variant, claim), IrisUi.spaced(context, sectionGap));
        wrapper.addView(evidenceSummary(context, variant, claim), IrisUi.spaced(context, sectionGap));
        wrapper.addView(IrisUi.eyebrow(context, "Evidence Sources"), IrisUi.spaced(context, sectionGap));

        if (claim.sources.isEmpty()) {
            TextView empty = IrisUi.muted(context, "No valid evidence link found.", 12.5f);
            empty.setGravity(Gravity.CENTER);
            int emptyPaddingVertical = compact ? 13 : 14;
            empty.setPadding(
                IrisUi.dp(context, 12),
                IrisUi.dp(context, emptyPaddingVertical),
                IrisUi.dp(context, 12),
                IrisUi.dp(context, emptyPaddingVertical)
            );
            empty.setBackground(IrisUi.bordered(context, IrisUi.BG, 14, IrisUi.BORDER));
            wrapper.addView(empty, IrisUi.spaced(context, itemGap));
            return wrapper;
        }

        int hidden = 0;
        for (int index = 0; index < claim.sources.size(); index += 1) {
            if (!sourcesExpanded && index >= 3) {
                hidden = claim.sources.size() - index;
                break;
            }
            wrapper.addView(sourceCard(context, variant, claim.sources.get(index)),
                IrisUi.spaced(context, itemGap));
        }
        if (hidden > 0) {
            Button showMore = IrisUi.ghostButton(context, "Show " + hidden + " more");
            showMore.setOnClickListener(view -> onShowMore.run());
            wrapper.addView(showMore, IrisUi.spaced(context, itemGap));
        }
        return wrapper;
    }

    static View skippedNote(Context context, IrisResultData resultData) {
        StringBuilder message = new StringBuilder("IRIS skipped ");
        for (int index = 0; index < resultData.skippedSegments.size(); index += 1) {
            IrisResultData.SkippedSegment segment = resultData.skippedSegments.get(index);
            if (index > 0) message.append(index == resultData.skippedSegments.size() - 1 ? " and " : ", ");
            message.append(segment.count).append(" ").append(segment.label);
            if (segment.count != 1) message.append("s");
        }
        message.append(" because they were not independently checkable.");

        TextView note = IrisUi.muted(context, message.toString(), 12);
        note.setGravity(Gravity.CENTER);
        note.setPadding(IrisUi.dp(context, 12), IrisUi.dp(context, 12),
            IrisUi.dp(context, 12), IrisUi.dp(context, 12));
        note.setBackground(IrisUi.bordered(context, IrisUi.BG, 14, IrisUi.BORDER));
        return note;
    }

    static View errorCard(Context context, Variant variant, String message) {
        boolean compact = variant == Variant.COMPACT;
        float textSize = compact ? 13.5f : 14;
        int paddingH = compact ? 16 : 18;
        int paddingV = compact ? 14 : 16;

        TextView error = IrisUi.text(context, message, textSize, Color.rgb(153, 27, 27), Typeface.BOLD);
        error.setPadding(IrisUi.dp(context, paddingH), IrisUi.dp(context, paddingV),
            IrisUi.dp(context, paddingH), IrisUi.dp(context, paddingV));
        error.setBackground(IrisUi.bordered(context, Color.rgb(254, 242, 242), 14,
            Color.rgb(252, 165, 165)));
        return error;
    }

    private static Button roundNavButton(Context context, String label, float textSize) {
        Button button = new Button(context);
        button.setText(label);
        button.setTextSize(textSize);
        button.setTextColor(IrisUi.VIOLET);
        button.setAllCaps(false);
        button.setBackground(IrisUi.bordered(context, IrisUi.CARD, 999, IrisUi.BORDER));
        IrisUi.touchFeedback(button, 999);
        return button;
    }

    private static View claimBox(Context context, Variant variant, String claimText,
                                 boolean imageInput) {
        float quoteSize = variant == Variant.COMPACT ? 15.5f : 16;

        LinearLayout box = IrisUi.horizontal(context, 0);
        box.setGravity(Gravity.CENTER_VERTICAL);
        box.setBackground(IrisUi.bordered(context, IrisUi.BLUE_BG, 14, IrisUi.BLUE_OUTLINE));

        View accent = new View(context);
        accent.setBackgroundColor(IrisUi.BLUE_BORDER);
        box.addView(accent, new LinearLayout.LayoutParams(IrisUi.dp(context, 4),
            LinearLayout.LayoutParams.MATCH_PARENT));

        LinearLayout copy = IrisUi.vertical(context, 12);
        if (imageInput) {
            copy.addView(IrisUi.eyebrow(context, "Text extracted from image"), IrisUi.matchWrap());
        }

        TextView quote = new TextView(context);
        quote.setText(TextUtils.isEmpty(claimText) ? "No claim text returned." : claimText);
        quote.setTextColor(IrisUi.TEXT);
        quote.setTextSize(quoteSize);
        quote.setTypeface(Typeface.SERIF, Typeface.ITALIC);
        quote.setLineSpacing(0, 1.12f);
        copy.addView(quote, IrisUi.matchWrap());
        box.addView(copy, IrisUi.rowWeight(1));
        return box;
    }

    private static View politicalFlag(Context context, Variant variant) {
        boolean compact = variant == Variant.COMPACT;
        int rowPadding = compact ? 11 : 12;
        int iconSize = compact ? 32 : 34;
        float iconTextSize = compact ? 17f : 18f;
        float titleSize = compact ? 13.5f : 14;
        float bodySize = compact ? 11.5f : 12;

        LinearLayout flag = IrisUi.horizontal(context, rowPadding);
        flag.setBackground(IrisUi.bordered(context, IrisUi.ORANGE_BG, 14, IrisUi.ORANGE_BORDER));

        TextView icon = new TextView(context);
        icon.setText("!");
        icon.setTextSize(iconTextSize);
        icon.setGravity(Gravity.CENTER);
        icon.setTextColor(IrisUi.ORANGE);
        icon.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        icon.setBackground(IrisUi.rounded(context, Color.WHITE, 999));
        flag.addView(icon, IrisUi.fixed(context, iconSize, iconSize));

        LinearLayout copy = IrisUi.vertical(context, 0);
        copy.addView(IrisUi.text(context, "Politically Sensitive", titleSize, IrisUi.ORANGE,
            Typeface.BOLD), IrisUi.matchWrap());
        copy.addView(IrisUi.text(context, "Apply extra scrutiny before sharing.", bodySize,
            IrisUi.ORANGE, Typeface.NORMAL), IrisUi.matchWrap());
        flag.addView(copy, IrisUi.rowWeight(1));
        return flag;
    }

    private static View verdictCard(Context context, Variant variant, IrisResultData.ClaimItem claim) {
        boolean compact = variant == Variant.COMPACT;
        int rowPadding = compact ? 13 : 14;
        int iconSize = compact ? 40 : 42;
        float iconTextSize = compact ? 17f : 18f;
        float verdictSize = compact ? 17f : 18f;
        float messageSize = compact ? 13f : 13.5f;

        LinearLayout card = IrisUi.horizontal(context, rowPadding);
        int color = IrisUi.verdictColor(claim.verdict);
        card.setBackground(IrisUi.bordered(context, IrisUi.verdictBackground(claim.verdict), 14,
            IrisUi.verdictBorder(claim.verdict)));

        TextView icon = new TextView(context);
        icon.setText(IrisUi.verdictIcon(claim.verdict));
        icon.setTextSize(iconTextSize);
        icon.setTextColor(color);
        icon.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        icon.setGravity(Gravity.CENTER);
        card.addView(icon, IrisUi.fixed(context, iconSize, iconSize));

        LinearLayout copy = IrisUi.vertical(context, 0);
        copy.addView(IrisUi.text(context, claim.verdict, verdictSize, color, Typeface.BOLD),
            IrisUi.matchWrap());
        copy.addView(IrisUi.text(context, claim.message, messageSize, color, Typeface.NORMAL),
            IrisUi.matchWrap());
        card.addView(copy, IrisUi.rowWeight(1));
        return card;
    }

    private static View evidenceSummary(Context context, Variant variant,
                                        IrisResultData.ClaimItem claim) {
        boolean compact = variant == Variant.COMPACT;
        int pillWidth = compact ? 74 : 78;
        int pillHeight = compact ? 32 : 34;
        float pillTextSize = compact ? 12.5f : 13;
        float labelSize = compact ? 12.5f : 13;

        LinearLayout row = IrisUi.horizontal(context, 0);

        TextView pill = new TextView(context);
        pill.setText(claim.evidenceCount + " of " + claim.evidenceTotal);
        pill.setTextColor(Color.WHITE);
        pill.setTextSize(pillTextSize);
        pill.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        pill.setGravity(Gravity.CENTER);
        pill.setBackground(IrisUi.gradient(context, 999));
        row.addView(pill, IrisUi.fixed(context, pillWidth, pillHeight));

        TextView label = IrisUi.muted(context,
            claim.evidenceCount == 1 ? " evidence source used" : " evidence sources used", labelSize);
        row.addView(label, IrisUi.rowWeight(1));
        return row;
    }

    private static View sourceCard(Context context, Variant variant, IrisResultData.SourceItem source) {
        boolean compact = variant == Variant.COMPACT;
        int cardPadding = compact ? 11 : 12;
        float outletSize = compact ? 11.5f : 12;
        float dateSize = compact ? 10.5f : 11;
        float titleSize = compact ? 13f : 13.5f;
        float linkSize = compact ? 11.5f : 12;
        int linkGap = compact ? 5 : 6;

        LinearLayout card = IrisUi.vertical(context, cardPadding);
        card.setBackground(IrisUi.bordered(context, IrisUi.CARD, 18, IrisUi.BORDER));
        card.setClickable(true);
        IrisUi.touchFeedback(card, 18);
        card.setOnClickListener(view -> {
            Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(source.url));
            // The overlay panel runs in a Service, which needs the new-task flag an
            // Activity launch gets for free.
            if (!(context instanceof Activity)) {
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            }
            context.startActivity(intent);
        });

        LinearLayout meta = IrisUi.horizontal(context, 0);
        meta.addView(IrisUi.text(context, source.outlet, outletSize, IrisUi.VIOLET, Typeface.BOLD),
            IrisUi.rowWeight(1));
        TextView date = IrisUi.muted(context, source.date, dateSize);
        date.setGravity(Gravity.END);
        meta.addView(date, IrisUi.rowWeight(1));
        card.addView(meta, IrisUi.matchWrap());

        TextView title = IrisUi.text(context, source.title, titleSize, IrisUi.TEXT, Typeface.BOLD);
        card.addView(title, IrisUi.spaced(context, linkGap));

        TextView link = IrisUi.text(context, "Read full article", linkSize, IrisUi.VIOLET,
            Typeface.BOLD);
        card.addView(link, IrisUi.spaced(context, linkGap));
        return card;
    }
}
