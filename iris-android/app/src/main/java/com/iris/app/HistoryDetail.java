package com.iris.app;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.graphics.Typeface;
import android.net.Uri;
import android.text.TextUtils;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.List;

/**
 * The detail block a history row expands into, shared by the bubble panel and the
 * history screen so both surfaces render the same stored check the same way.
 *
 * The stored payload is parsed here on first expand, never up front: scrolling a list
 * of checks should not pay for JSON that may never be opened.
 *
 * Structure mirrors the extension's history detail: one block per claim, each carrying
 * its verdict, claim, explanation, evidence count, and a source list capped behind a
 * "Show N more" control so a long evidence list never buries the rest of the check.
 * Several claims are numbered "Claim N of M" like the result screen's pager label.
 */
final class HistoryDetail {
    private HistoryDetail() {}

    /** Matches the extension's HISTORY_SOURCE_LIMIT: first three links, rest folded. */
    private static final int HISTORY_SOURCE_LIMIT = 3;

    /**
     * Builds the expanded detail for one entry. `openFullResult` is the escape hatch
     * back to ResultActivity; the caller owns that launch because the bubble has to
     * fold itself away first while the activity must not.
     */
    static View build(Context context, HistoryStore.HistoryEntry entry, String checkedAtLabel, Runnable openFullResult) {
        // Same parse ResultActivity runs, so verdict, claim and links can never drift
        // between the inline view and the full screen it links to.
        IrisResultData data = IrisResultData.parse(entry.rawJson, entry.fallback, entry.inputType);

        LinearLayout detail = IrisUi.vertical(context, 12);
        detail.setBackground(IrisUi.bordered(context, IrisUi.CARD, 14, IrisUi.BORDER));

        List<IrisResultData.ClaimItem> claims = data.claims;
        if (claims.isEmpty()) {
            // A payload with no claims still says what it can instead of rendering nothing.
            String text = TextUtils.isEmpty(entry.fallback)
                ? "No claim details were stored for this check."
                : entry.fallback;
            detail.addView(IrisUi.muted(context, text, 12), IrisUi.spaced(context, 8));
        } else {
            for (int index = 0; index < claims.size(); index += 1) {
                if (index > 0) {
                    // Divider between claims, matching the extension's per-claim border.
                    View divider = new View(context);
                    divider.setBackgroundColor(IrisUi.BORDER);
                    LinearLayout.LayoutParams lineParams = new LinearLayout.LayoutParams(
                        LinearLayout.LayoutParams.MATCH_PARENT, IrisUi.dp(context, 1));
                    lineParams.topMargin = IrisUi.dp(context, 4);
                    lineParams.bottomMargin = IrisUi.dp(context, 4);
                    detail.addView(divider, lineParams);
                }
                String claimLabel = claims.size() > 1
                    ? "Claim " + (index + 1) + " of " + claims.size()
                    : null;
                detail.addView(claimBlock(context, claims.get(index), claimLabel), IrisUi.matchWrap());
            }
        }

        detail.addView(checkedRow(context, checkedAtLabel), IrisUi.spaced(context, 8));

        Button open = IrisUi.ghostButton(context, "Open full result");
        open.setOnClickListener(view -> openFullResult.run());
        detail.addView(open, IrisUi.spaced(context, 8));
        return detail;
    }

    /** One claim: optional "Claim N of M" label, badge, quote, explanation, evidence, sources. */
    private static View claimBlock(Context context, IrisResultData.ClaimItem claim, String claimLabel) {
        LinearLayout block = IrisUi.vertical(context, 8);

        if (claimLabel != null) {
            block.addView(IrisUi.eyebrow(context, claimLabel), IrisUi.matchWrap());
        }

        block.addView(verdictBadge(context, claim.verdict), IrisUi.matchWrap());

        if (!TextUtils.isEmpty(claim.claimText)) {
            block.addView(claimBox(context, claim.claimText), IrisUi.spaced(context, 4));
        }

        if (!TextUtils.isEmpty(claim.message)) {
            TextView message = IrisUi.text(context, claim.message, 13, IrisUi.TEXT, Typeface.NORMAL);
            message.setLineSpacing(0, 1.4f);
            block.addView(message, IrisUi.spaced(context, 4));
        }

        String countLabel = claim.evidenceCount + " evidence "
            + (claim.evidenceCount == 1 ? "source" : "sources");
        block.addView(IrisUi.muted(context, countLabel, 11.5f), IrisUi.spaced(context, 4));

        block.addView(sourceList(context, claim.sources), IrisUi.spaced(context, 4));
        return block;
    }

    /**
     * First HISTORY_SOURCE_LIMIT links shown, the rest revealed in place when the
     * control is tapped. The extension keeps collapsed links in the DOM and toggles a
     * class; keeping them here with GONE does the same job without rebuilding the list
     * the reader is looking at.
     */
    private static View sourceList(Context context, List<IrisResultData.SourceItem> sources) {
        LinearLayout list = IrisUi.vertical(context, 6);
        if (sources.isEmpty()) {
            list.addView(IrisUi.muted(context, "No article links stored for this check.", 12), IrisUi.matchWrap());
            return list;
        }

        List<View> hidden = new ArrayList<>();
        for (int index = 0; index < sources.size(); index += 1) {
            View link = sourceLink(context, sources.get(index));
            if (index >= HISTORY_SOURCE_LIMIT) {
                link.setVisibility(View.GONE);
                hidden.add(link);
            }
            list.addView(link, IrisUi.matchWrap());
        }

        if (!hidden.isEmpty()) {
            Button more = IrisUi.ghostButton(context, "Show " + hidden.size() + " more");
            more.setOnClickListener(view -> {
                for (View link : hidden) link.setVisibility(View.VISIBLE);
                list.removeView(more);
            });
            list.addView(more, IrisUi.matchWrap());
        }
        return list;
    }

    /**
     * Expands or collapses the detail container. `onSettled` fires once the container's
     * height is final, so the overlay panel can re-derive its height cap after a
     * collapse instead of being left holding the taller pre-collapse measurement.
     *
     * Motion decides the transition, never the result: reduced-motion users get the
     * same instant swap the rest of the app uses.
     */
    static void setExpanded(View detail, boolean expanded, Runnable onSettled) {
        detail.animate().cancel();
        if (!IrisMotion.animationsEnabled()) {
            detail.setAlpha(1f);
            detail.setVisibility(expanded ? View.VISIBLE : View.GONE);
            onSettled.run();
            return;
        }

        if (expanded) {
            detail.setVisibility(View.VISIBLE);
            detail.setAlpha(0f);
            // Height is final the moment the container becomes visible, so the caller
            // can re-measure immediately instead of waiting out the fade.
            detail.animate().alpha(1f).setDuration(160).start();
            onSettled.run();
        } else {
            detail.animate().alpha(0f).setDuration(120)
                .withEndAction(() -> {
                    detail.setVisibility(View.GONE);
                    detail.setAlpha(1f);
                    onSettled.run();
                })
                .start();
        }
    }

    /** Row label plus aria-style expanded state, so TalkBack readers hear the toggle. */
    static String rowDescription(String verdict, String preview, String checkedAtLabel, boolean expanded) {
        StringBuilder description = new StringBuilder(TextUtils.isEmpty(verdict) ? "Result" : verdict);
        if (!TextUtils.isEmpty(preview)) description.append(": ").append(preview);
        if (!TextUtils.isEmpty(checkedAtLabel)) description.append(", checked ").append(checkedAtLabel);
        description.append(expanded ? ", details expanded" : ", details collapsed");
        return description.toString();
    }

    private static View verdictBadge(Context context, String verdict) {
        int color = IrisUi.verdictColor(verdict);
        LinearLayout badge = IrisUi.horizontal(context, 10);
        badge.setBackground(IrisUi.bordered(context, IrisUi.verdictBackground(verdict), 14, IrisUi.verdictBorder(verdict)));

        TextView icon = new TextView(context);
        icon.setText(IrisUi.verdictIcon(verdict));
        icon.setTextSize(15);
        icon.setTextColor(color);
        icon.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        icon.setGravity(Gravity.CENTER);
        badge.addView(icon, IrisUi.fixed(context, 36, 36));

        LinearLayout copy = IrisUi.vertical(context, 0);
        copy.addView(IrisUi.eyebrow(context, "Verdict"), IrisUi.matchWrap());
        copy.addView(IrisUi.text(context, verdict, 15, color, Typeface.BOLD), IrisUi.matchWrap());
        LinearLayout.LayoutParams copyParams = IrisUi.rowWeight(1);
        copyParams.leftMargin = IrisUi.dp(context, 10);
        badge.addView(copy, copyParams);
        return badge;
    }

    /** Quote box mirroring ResultActivity's claim box, scaled for a nested card. */
    private static View claimBox(Context context, String claimText) {
        LinearLayout box = IrisUi.horizontal(context, 0);
        box.setGravity(Gravity.CENTER_VERTICAL);
        box.setBackground(IrisUi.bordered(context, IrisUi.BLUE_BG, 14, IrisUi.BLUE_OUTLINE));

        View accent = new View(context);
        accent.setBackgroundColor(IrisUi.BLUE_BORDER);
        box.addView(accent, new LinearLayout.LayoutParams(IrisUi.dp(context, 4), LinearLayout.LayoutParams.MATCH_PARENT));

        LinearLayout copy = IrisUi.vertical(context, 10);
        TextView quote = new TextView(context);
        quote.setText(claimText);
        quote.setTextColor(IrisUi.TEXT);
        quote.setTextSize(14);
        quote.setTypeface(Typeface.SERIF, Typeface.ITALIC);
        quote.setLineSpacing(0, 1.12f);
        copy.addView(quote, IrisUi.matchWrap());
        box.addView(copy, IrisUi.rowWeight(1));
        return box;
    }

    private static View checkedRow(Context context, String checkedAtLabel) {
        LinearLayout meta = IrisUi.horizontal(context, 0);
        meta.addView(IrisUi.eyebrow(context, "Checked"), IrisUi.rowWeight(1));
        TextView date = IrisUi.muted(context, checkedAtLabel == null ? "" : checkedAtLabel, 11.5f);
        date.setGravity(Gravity.END);
        meta.addView(date, IrisUi.rowWeight(1));
        return meta;
    }

    /** Compact article link that opens in the browser exactly like the result screen's source card. */
    private static View sourceLink(Context context, IrisResultData.SourceItem source) {
        LinearLayout card = IrisUi.vertical(context, 10);
        card.setBackground(IrisUi.bordered(context, IrisUi.BG, 14, IrisUi.BORDER));
        card.setClickable(true);
        IrisUi.touchFeedback(card, 14);
        card.setOnClickListener(view -> {
            Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(source.url));
            // The bubble panel runs in a Service, so its links need the new-task flag
            // that an Activity launch gets for free.
            if (!(context instanceof Activity)) {
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            }
            context.startActivity(intent);
        });

        LinearLayout meta = IrisUi.horizontal(context, 0);
        meta.addView(IrisUi.text(context, source.outlet, 11.5f, IrisUi.VIOLET, Typeface.BOLD), IrisUi.rowWeight(1));
        TextView date = IrisUi.muted(context, source.date, 10.5f);
        date.setGravity(Gravity.END);
        meta.addView(date, IrisUi.rowWeight(1));
        card.addView(meta, IrisUi.matchWrap());

        card.addView(IrisUi.text(context, source.title, 13, IrisUi.TEXT, Typeface.BOLD), IrisUi.spaced(context, 5));
        card.addView(IrisUi.text(context, "Read full article", 11.5f, IrisUi.VIOLET, Typeface.BOLD), IrisUi.spaced(context, 5));
        return card;
    }
}
