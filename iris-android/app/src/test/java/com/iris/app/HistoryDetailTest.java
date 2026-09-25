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
            () -> {}
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
            () -> {}
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
            () -> opened.set(true)
        );

        View open = findWithText(detail, "Open full result");
        assertEquals("expected an 'Open full result' control", true, open != null);
        open.performClick();

        assertTrue("the escape hatch should hand off to ResultActivity", opened.get());
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
