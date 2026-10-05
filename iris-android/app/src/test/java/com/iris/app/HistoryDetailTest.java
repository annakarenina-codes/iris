package com.iris.app;

import android.os.Looper;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import static org.robolectric.Shadows.shadowOf;

@RunWith(RobolectricTestRunner.class)
@Config(sdk = 34)
public class HistoryDetailTest {

    @Test
    public void buildNumbersEveryClaimWhenCheckHoldsSeveral() throws Exception {
        View detail = HistoryDetail.build(
            RuntimeEnvironment.getApplication(),
            entry(threeClaimJson(), ""),
            "2026-09-25 13:00",
            () -> {},
            null
        );

        List<String> texts = textsIn(detail);
        assertTrue(texts.contains("Claim 1 of 3"));
        assertTrue(texts.contains("Claim 2 of 3"));
        assertTrue(texts.contains("Claim 3 of 3"));
        // Every claim's own verdict and quote render, not just the first one.
        assertTrue(texts.contains("First claim text"));
        assertTrue(texts.contains("Second claim text"));
        assertTrue(texts.contains("Third claim text"));
    }

    @Test
    public void buildOmitsClaimNumberForSingleClaim() throws Exception {
        View detail = HistoryDetail.build(
            RuntimeEnvironment.getApplication(),
            entry(singleClaimJson(), ""),
            "2026-09-25 13:00",
            () -> {},
            null
        );

        for (String text : textsIn(detail)) {
            assertFalse(
                "a one-claim check should not label itself: " + text,
                text.matches("Claim \\d+ of \\d+")
            );
        }
    }

    @Test
    public void buildFiresEscapeHatchFromOpenFullResult() throws Exception {
        AtomicBoolean opened = new AtomicBoolean(false);
        View detail = HistoryDetail.build(
            RuntimeEnvironment.getApplication(),
            entry(singleClaimJson(), ""),
            "2026-09-25 13:00",
            () -> opened.set(true),
            null
        );

        View open = findWithText(detail, "Open full result");
        assertEquals("expected an 'Open full result' control", true, open != null);
        open.performClick();

        assertTrue("the escape hatch should hand off to ResultActivity", opened.get());
    }

    @Test
    public void buildHandsSourceLinksToTheHostBeforeOpeningTheArticle() throws Exception {
        AtomicBoolean hostPutAway = new AtomicBoolean(false);
        View detail = HistoryDetail.build(
            RuntimeEnvironment.getApplication(),
            entry(singleClaimJsonWithSource(), ""),
            "2026-09-25 13:00",
            () -> {},
            () -> hostPutAway.set(true)
        );

        View link = sourceCard(detail);
        assertEquals("expected a clickable source link", true, link != null);
        link.performClick();

        assertTrue(
            "the bubble panel must put itself away before the browser opens",
            hostPutAway.get()
        );
    }

    @Test
    public void setExpandedTogglesDetailVisibility() {
        View detail = new android.widget.LinearLayout(RuntimeEnvironment.getApplication());

        HistoryDetail.setExpanded(detail, true, () -> {});
        assertEquals(View.VISIBLE, detail.getVisibility());

        HistoryDetail.setExpanded(detail, false, () -> {});
        // End-of-collapse action runs on the main looper when animations are on,
        // and immediately when they are off; idleing covers both.
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(200));
        assertEquals(View.GONE, detail.getVisibility());
    }

    @Test
    public void rowDescriptionMarksExpandedState() {
        String expanded = HistoryDetail.rowDescription("Verified", "some claim", "2026-09-25 13:00", true);
        String collapsed = HistoryDetail.rowDescription("Verified", "some claim", "2026-09-25 13:00", false);

        assertTrue(expanded.endsWith(", details expanded"));
        assertTrue(collapsed.endsWith(", details collapsed"));
        assertTrue(expanded.startsWith("Verified: some claim"));
    }

    @Test
    public void buildRendersStoredSharedImageSourceUrl() throws Exception {
        View detail = HistoryDetail.build(
            RuntimeEnvironment.getApplication(),
            entry(singleClaimJsonWithSourceUrl(), ""),
            "2026-09-25 13:00",
            () -> {},
            null
        );

        assertTrue(
            "the share's source URL must survive into history detail",
            findWithText(detail, "https://www.example.com/post/42") != null
        );
    }

    @Test
    public void buildOmitsSourceUrlRowWhenNoneWasShared() throws Exception {
        View detail = HistoryDetail.build(
            RuntimeEnvironment.getApplication(),
            entry(singleClaimJson(), ""),
            "2026-09-25 13:00",
            () -> {},
            null
        );

        for (String text : textsIn(detail)) {
            assertFalse(
                "gallery checks carry no source URL, so no row may render: " + text,
                text.equals("Image source")
            );
        }
    }

    @Test
    public void buildHandsSourceUrlTapToTheHostBeforeOpeningTheBrowser() throws Exception {
        AtomicBoolean hostPutAway = new AtomicBoolean(false);
        View detail = HistoryDetail.build(
            RuntimeEnvironment.getApplication(),
            entry(singleClaimJsonWithSourceUrl(), ""),
            "2026-09-25 13:00",
            () -> {},
            () -> hostPutAway.set(true)
        );

        View row = clickableAncestorOf(findWithText(detail, "https://www.example.com/post/42"));
        assertEquals("expected a clickable source URL row", true, row != null);
        row.performClick();

        assertTrue(
            "the bubble panel must put itself away before the browser opens",
            hostPutAway.get()
        );
    }

    @Test
    public void buildLeadsWithTheImageBadgeAheadOfTheClaims() throws Exception {
        View detail = HistoryDetail.build(
            RuntimeEnvironment.getApplication(),
            entry(imageAuthenticityJson(true), ""),
            "2026-09-25 13:00",
            () -> {},
            null
        );

        List<String> texts = textsIn(detail);
        assertTrue(texts.contains("AI-generated image"));
        assertTrue(texts.contains("SightEngine's AI-image detector flagged this image."));
        assertTrue(texts.contains("AI probability: 99%"));
        assertTrue("the badge must lead, ahead of the claim text",
            texts.indexOf("AI-generated image") < texts.indexOf("First claim text"));
    }

    @Test
    public void buildNamesTheDetectorInTheHonestClearState() throws Exception {
        View detail = HistoryDetail.build(
            RuntimeEnvironment.getApplication(),
            entry(imageAuthenticityJson(false), ""),
            "2026-09-25 13:00",
            () -> {},
            null
        );

        List<String> texts = textsIn(detail);
        assertTrue(texts.contains("No AI detected"));
        assertTrue(texts.contains(
            "SightEngine did not flag this image. That is not proof it is authentic."));
        assertFalse("the clear state never publishes a score",
            texts.contains("AI probability: 0%"));
    }

    @Test
    public void buildAddsNoBadgeForATextCheck() throws Exception {
        View detail = HistoryDetail.build(
            RuntimeEnvironment.getApplication(),
            entry(singleClaimJson(), ""),
            "2026-09-25 13:00",
            () -> {},
            null
        );

        assertFalse(textsIn(detail).contains("AI-generated image"));
    }

    private static String imageAuthenticityJson(boolean aiGenerated) throws Exception {
        JSONObject ai = new JSONObject();
        ai.put("status", "ok");
        ai.put("is_ai_generated", aiGenerated);
        ai.put("confidence", aiGenerated ? 0.99 : 0.0);
        ai.put("model", "SightEngine");

        JSONObject claim = new JSONObject();
        claim.put("claim_text", "First claim text");
        claim.put("verdict", "Verified");

        JSONObject payload = new JSONObject();
        payload.put("claims", new JSONArray().put(claim));
        payload.put("image_authenticity_checked", true);
        payload.put("ai_generated", ai);
        return payload.toString();
    }

    private static HistoryStore.HistoryEntry entry(String rawJson, String fallback) {
        HistoryStore.HistoryEntry entry = new HistoryStore.HistoryEntry();
        entry.rawJson = rawJson;
        entry.fallback = fallback;
        return entry;
    }

    private static String singleClaimJson() throws Exception {
        JSONObject claim = new JSONObject();
        claim.put("claim_text", "First claim text");
        claim.put("verdict", "Verified");

        JSONObject payload = new JSONObject();
        payload.put("claims", new JSONArray().put(claim));
        return payload.toString();
    }

    /** One claim carrying a real source, so a link actually renders to click. */
    private static String singleClaimJsonWithSource() throws Exception {
        JSONObject source = new JSONObject();
        source.put("url", "https://www.rappler.com/nation/example");
        source.put("outlet", "Rappler");
        source.put("title", "Example article");

        JSONObject claim = new JSONObject();
        claim.put("claim_text", "First claim text");
        claim.put("verdict", "Verified");
        claim.put("sources", new JSONArray().put(source));

        JSONObject payload = new JSONObject();
        payload.put("claims", new JSONArray().put(claim));
        return payload.toString();
    }

    /** One claim plus the source_url a share caption contributed. */
    private static String singleClaimJsonWithSourceUrl() throws Exception {
        JSONObject claim = new JSONObject();
        claim.put("claim_text", "First claim text");
        claim.put("verdict", "Verified");

        JSONObject payload = new JSONObject();
        payload.put("claims", new JSONArray().put(claim));
        payload.put("source_url", "https://www.example.com/post/42");
        return payload.toString();
    }

    private static String threeClaimJson() throws Exception {
        JSONArray claims = new JSONArray();
        String[] texts = {"First claim text", "Second claim text", "Third claim text"};
        String[] verdicts = {"Verified", "Refuted", "Not Found"};
        for (int index = 0; index < texts.length; index += 1) {
            JSONObject claim = new JSONObject();
            claim.put("claim_text", texts[index]);
            claim.put("verdict", verdicts[index]);
            claims.put(claim);
        }

        JSONObject payload = new JSONObject();
        payload.put("claims", claims);
        return payload.toString();
    }

    private static List<String> textsIn(View view) {
        List<String> texts = new ArrayList<>();
        collectTexts(view, texts);
        return texts;
    }

    private static void collectTexts(View view, List<String> texts) {
        if (view instanceof TextView) {
            texts.add(((TextView) view).getText().toString());
        }
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int index = 0; index < group.getChildCount(); index += 1) {
                collectTexts(group.getChildAt(index), texts);
            }
        }
    }

    /**
     * The source card wraps its "Read full article" label; the label itself is a plain
     * TextView, so clicking it proves nothing. Walk out to the card that owns the listener.
     */
    private static View sourceCard(View root) {
        return clickableAncestorOf(findWithText(root, "Read full article"));
    }

    /** Walks from a label out to the nearest ancestor that owns a click listener. */
    private static View clickableAncestorOf(View label) {
        if (label == null) return null;
        Object parent = label.getParent();
        while (parent instanceof View) {
            View view = (View) parent;
            if (view.isClickable()) return view;
            parent = view.getParent();
        }
        return null;
    }

    private static View findWithText(View view, String wanted) {
        if (view instanceof TextView && wanted.equals(((TextView) view).getText().toString())) {
            return view;
        }
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int index = 0; index < group.getChildCount(); index += 1) {
                View found = findWithText(group.getChildAt(index), wanted);
                if (found != null) return found;
            }
        }
        return null;
    }
}
