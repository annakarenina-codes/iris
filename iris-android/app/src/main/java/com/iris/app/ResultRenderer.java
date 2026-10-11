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
                           IrisResultData.ImageAuthenticity authenticity,
                           boolean imageInput, String sourceUrl, boolean sourcesExpanded,
                           Runnable onShowMore, Runnable onLinkClick) {
        boolean compact = variant == Variant.COMPACT;
        int sectionGap = compact ? 10 : 12;
        int itemGap = 8;

        LinearLayout wrapper = IrisUi.vertical(context, 0);
        // Leads the panel the same way the extension leads the result: for an image
        // check, whether the image was assessed at all outranks the extracted text.
        // The claim box carries the section gap when it follows the authenticity card;
        // matchWrap() has no margin, so without it the two cards sit flush together.
        if (authenticity != null) {
            wrapper.addView(authenticityCard(context, variant, authenticity), IrisUi.matchWrap());
            wrapper.addView(claimBox(context, variant, claim.claimText, imageInput),
                IrisUi.spaced(context, sectionGap));
        } else {
            wrapper.addView(claimBox(context, variant, claim.claimText, imageInput),
                IrisUi.matchWrap());
        }

        // The page the shared image came from, carried in the share itself. Sits with
        // the claim box because both describe the input, not the verdict.
        if (!TextUtils.isEmpty(sourceUrl)) {
            wrapper.addView(sourceUrlRow(context, variant, sourceUrl, onLinkClick),
                IrisUi.spaced(context, sectionGap));
        }

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
            wrapper.addView(sourceCard(context, variant, claim.sources.get(index), onLinkClick),
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

    /**
     * The page the shared image came from, as one tappable row. The URL opens exactly
     * like a source card's link — same ACTION_VIEW, same new-task flag for the service
     * context — so "where did this image come from" is one tap away instead of gone.
     */
    private static View sourceUrlRow(Context context, Variant variant, String sourceUrl,
                                     Runnable onLinkClick) {
        boolean compact = variant == Variant.COMPACT;
        int rowPadding = compact ? 11 : 12;

        LinearLayout row = IrisUi.vertical(context, rowPadding);
        row.setBackground(IrisUi.bordered(context, IrisUi.CARD, 14, IrisUi.BORDER));
        row.setClickable(true);
        IrisUi.touchFeedback(row, 14);
        row.setOnClickListener(view -> {
            if (onLinkClick != null) onLinkClick.run();
            Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(sourceUrl));
            if (!(context instanceof Activity)) {
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            }
            context.startActivity(intent);
        });

        row.addView(IrisUi.eyebrow(context, "Image source"), IrisUi.matchWrap());
        TextView url = IrisUi.text(context, sourceUrl, compact ? 11.5f : 12, IrisUi.VIOLET,
            Typeface.BOLD);
        url.setSingleLine(true);
        url.setEllipsize(TextUtils.TruncateAt.END);
        row.addView(url, IrisUi.matchWrap());
        return row;
    }

    /**
     * Three states, not two. "Not assessed" is a real outcome and must stay visible:
     * folding it into the clear state would draw an unrun check as a passed one, which
     * is the false reassurance the newsroom rule exists to prevent. The neutral copy
     * for the clear state says so explicitly rather than calling the image authentic.
     *
     * These cards use the day-only GREEN/RED/GRAY tokens on purpose, exactly like
     * politicalFlag: those tokens never reassign in applyTheme, so a light card with
     * dark ink stays readable in both themes instead of flipping with the surface.
     */
    static View authenticityCard(Context context, Variant variant,
                                 IrisResultData.ImageAuthenticity info) {
        boolean compact = variant == Variant.COMPACT;
        int rowPadding = compact ? 11 : 12;
        int iconSize = compact ? 32 : 34;
        float iconTextSize = compact ? 15f : 16f;
        float titleSize = compact ? 13.5f : 14;
        float bodySize = compact ? 11.5f : 12;
        float scoreSize = compact ? 10.5f : 11;

        int background;
        int border;
        int ink;
        String icon;
        String title;
        String body;

        // genai's own call stays separate from the flags: the AI score only prints next
        // to genai's verdict, never beside a detector that is reporting something else.
        boolean aiGenerated = IrisResultData.ImageAuthenticity.AI_GENERATED.equals(info.state);
        IrisResultData.DetectorFlag deepfake =
            findFlag(info, IrisResultData.ImageAuthenticity.FLAG_DEEPFAKE);

        // Card colour answers ONE question — how worried is this about forgery — so only
        // genai and face swaps may set it. Added text is a weaker and far more common
        // claim (a news chyron, a watermark, an overlay are all "text added after the
        // shot"), so it gets its own muted line and never repaints the card: a signal
        // that fires on nearly every image is noise, and noise must not cry wolf.
        // The single exception stays — a face swap beside "No AI detected" would
        // contradict itself — so deepfake still takes the headline when genai is quiet.
        IrisResultData.DetectorFlag headline = null;
        if (!aiGenerated && deepfake != null) {
            headline = deepfake;
        }

        if (IrisResultData.ImageAuthenticity.NOT_ASSESSED.equals(info.state)) {
            background = IrisUi.GRAY_BG;
            border = IrisUi.GRAY_BORDER;
            ink = IrisUi.GRAY;
            icon = "?";
            title = "Not assessed";
            body = "IRIS could not run image detection on this image.";
        } else if (aiGenerated || deepfake != null) {
            background = IrisUi.RED_BG;
            border = IrisUi.RED_BORDER;
            ink = IrisUi.RED;
            icon = "!";
            if (aiGenerated) {
                title = "AI-generated image";
                // Three models run (genai, deepfake, embedded text); genai alone decides
                // THIS verdict, so the copy names it and never claims a second detector
                // or a manipulation/forensics check this pipeline does not perform.
                body = info.model.isEmpty()
                    ? "The AI-image detector flagged this image."
                    : info.model + "'s AI-image detector flagged this image.";
            } else {
                // The detector — not genai — is what fired, so its line becomes the
                // headline, and genai's own quiet reading is stated underneath rather
                // than hidden: each detector reports only what it saw.
                title = detectorFlagLabel(headline);
                body = (info.model.isEmpty()
                    ? "The AI-image detector did not flag this image."
                    : info.model + " did not flag this image.")
                    + " That is not proof it is authentic.";
            }
        } else {
            background = IrisUi.GREEN_BG;
            border = IrisUi.GREEN_BORDER;
            ink = IrisUi.GREEN;
            icon = "\u2713";
            title = "No AI detected";
            body = (info.model.isEmpty()
                ? "The AI-image detector did not flag this image."
                : info.model + " did not flag this image.")
                + " That is not proof it is authentic.";
        }

        LinearLayout row = IrisUi.horizontal(context, rowPadding);
        row.setBackground(IrisUi.bordered(context, background, 14, border));

        TextView mark = new TextView(context);
        mark.setText(icon);
        mark.setTextSize(iconTextSize);
        mark.setGravity(Gravity.CENTER);
        mark.setTextColor(ink);
        mark.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        mark.setBackground(IrisUi.rounded(context, Color.WHITE, 999));
        row.addView(mark, IrisUi.fixed(context, iconSize, iconSize));

        LinearLayout copy = IrisUi.vertical(context, 0);
        copy.addView(IrisUi.text(context, title, titleSize, ink, Typeface.BOLD), IrisUi.matchWrap());
        copy.addView(IrisUi.text(context, body, bodySize, ink, Typeface.NORMAL), IrisUi.matchWrap());

        if (IrisResultData.ImageAuthenticity.AI_GENERATED.equals(info.state) && info.confidence > 0) {
            copy.addView(IrisUi.text(context,
                "AI probability: " + Math.round(info.confidence * 100) + "%",
                scoreSize, ink, Typeface.BOLD), IrisUi.matchWrap());
        }

        // Every fired detector that is NOT already the headline rides as its own line in
        // amber — the one ink that stays distinguishable on any card tone, so added text
        // can be read without ever being able to repaint the card around it. It is an
        // independent observation of that detector, never folded into the verdict above
        // it or counted as a second vote on it.
        for (IrisResultData.DetectorFlag flag : info.flags) {
            if (flag == headline) continue;
            copy.addView(IrisUi.text(context, detectorFlagLabel(flag),
                scoreSize, IrisUi.ORANGE, Typeface.BOLD), IrisUi.matchWrap());
        }

        // The row's padding only insets the card's outer edge. LinearLayout puts no gap
        // between children, so without an explicit margin the icon touches the title.
        LinearLayout.LayoutParams copyParams = IrisUi.rowWeight(1);
        copyParams.setMargins(IrisUi.dp(context, 10), 0, 0, 0);
        row.addView(copy, copyParams);
        return row;
    }

    /** Returns the fired flag of the given kind, or null when that detector stayed quiet. */
    private static IrisResultData.DetectorFlag findFlag(IrisResultData.ImageAuthenticity info, String kind) {
        for (IrisResultData.DetectorFlag flag : info.flags) {
            if (kind.equals(flag.kind)) return flag;
        }
        return null;
    }

    /**
     * Phrases one fired detector's line exactly as the extension's i18n copy does, so
     * the two surfaces never drift: an unknown kind still renders honestly as a flag
     * rather than being swallowed.
     */
    private static String detectorFlagLabel(IrisResultData.DetectorFlag flag) {
        int pct = (int) Math.round(flag.confidence * 100);
        if (IrisResultData.ImageAuthenticity.FLAG_EMBEDDED_TEXT.equals(flag.kind)) {
            return "Text added after capture: flagged (" + pct + "%)";
        }
        return "Face swap: flagged (" + pct + "%)";
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
        LinearLayout.LayoutParams flagParams = IrisUi.rowWeight(1);
        flagParams.setMargins(IrisUi.dp(context, 10), 0, 0, 0);
        flag.addView(copy, flagParams);
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
        LinearLayout.LayoutParams verdictCopyParams = IrisUi.rowWeight(1);
        verdictCopyParams.setMargins(IrisUi.dp(context, 10), 0, 0, 0);
        card.addView(copy, verdictCopyParams);
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

        // The pill and the label are siblings in a zero-padding row, so the gap has to be
        // a margin. The old leading space in the label was a stand-in for one and only
        // ever moved the text a couple of pixels.
        TextView label = IrisUi.muted(context,
            claim.evidenceCount == 1 ? "evidence source used" : "evidence sources used", labelSize);
        LinearLayout.LayoutParams labelParams = IrisUi.rowWeight(1);
        labelParams.setMargins(IrisUi.dp(context, 9), 0, 0, 0);
        row.addView(label, labelParams);
        return row;
    }

    private static View sourceCard(Context context, Variant variant, IrisResultData.SourceItem source,
                                  Runnable onLinkClick) {
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
            if (onLinkClick != null) onLinkClick.run();
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
