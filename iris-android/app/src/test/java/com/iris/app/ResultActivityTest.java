package com.iris.app;

import android.content.Intent;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.Robolectric;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;

import java.util.ArrayList;
import java.util.List;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

@RunWith(RobolectricTestRunner.class)
@Config(sdk = 34)
public class ResultActivityTest {

    @Test
    public void imageVerdictSurvivesAnEmptyClaimList() {
        String payload = "{"
            + "\"claims\": [],"
            + "\"image_authenticity_checked\": true,"
            + "\"ai_generated\": {\"status\": \"ok\", \"is_ai_generated\": true,"
            + "\"confidence\": 0.99, \"model\": \"SightEngine\"}"
            + "}";

        List<String> texts = textsForResult(payload, "image");

        assertTrue(texts.contains("AI-generated image"));
        assertTrue(texts.contains("SightEngine's AI-image detector flagged this image."));
        assertTrue(texts.contains("AI probability: 99%"));
        assertFalse("a real verdict must not be called an unreadable result",
            texts.contains("IRIS did not return a readable result."));
    }

    @Test
    public void textCheckWithoutDetectionKeysShowsNoImageBadge() {
        String payload = "{\"claims\": [], \"message\": \"No claims found.\"}";

        List<String> texts = textsForResult(payload, "text");

        // parse() synthesizes a fallback claim for an empty claim list, so this renders
        // the claim panel — and with no detection keys anywhere it must carry no badge
        // of any state.
        assertFalse(texts.contains("AI-generated image"));
        assertFalse(texts.contains("No AI detected"));
        assertFalse(texts.contains("Not assessed"));
    }

    @Test
    public void claimedListKeepsRidingTheBadgeInsideTheClaimPanel() {
        String payload = "{"
            + "\"claims\": [{\"claim_text\": \"A claim\", \"verdict\": \"Verified\"}],"
            + "\"image_authenticity_checked\": true,"
            + "\"ai_generated\": {\"status\": \"ok\", \"is_ai_generated\": false,"
            + "\"confidence\": 0.0, \"model\": \"SightEngine\"}"
            + "}";

        List<String> texts = textsForResult(payload, "image");

        assertTrue(texts.contains("A claim"));
        assertTrue(texts.contains("No AI detected"));
        assertTrue(texts.contains(
            "SightEngine did not flag this image. That is not proof it is authentic."));
    }

    @Test
    public void notAssessedPayloadsRenderTheHonestGrayStateNotAClearance() {
        String payload = "{"
            + "\"claims\": [],"
            + "\"image_authenticity_checked\": false,"
            + "\"ai_generated\": {\"status\": \"error\", \"error\": \"credentials\"}"
            + "}";

        List<String> texts = textsForResult(payload, "image");

        assertTrue(texts.contains("Not assessed"));
        assertTrue(texts.contains("IRIS could not run image detection on this image."));
        assertFalse(texts.contains("No AI detected"));
    }

    @Test
    public void addedTextAloneKeepsTheCardGreenAndSpeaksOnItsOwnLine() {
        String payload = "{"
            + "\"claims\": [],"
            + "\"image_authenticity_checked\": true,"
            + "\"ai_generated\": {\"status\": \"ok\", \"is_ai_generated\": false,"
            + "\"confidence\": 0.04, \"model\": \"SightEngine\"},"
            + "\"embedded_text\": {\"status\": \"ok\", \"is_suspicious\": true,"
            + "\"confidence\": 0.91, \"model\": \"text\"}"
            + "}";

        // Card colour answers "how worried is this about forgery", so added text alone
        // must not be allowed to repaint it — a routine news chyron would otherwise
        // become a standing alarm on nearly every image the user checks.
        assertEquals(IrisUi.GREEN, colorOfText(payload, "image", "No AI detected"));
        // It still speaks: its own line, in the amber ink that reads as a note rather
        // than an alarm, whatever tone the card around it has taken.
        assertEquals(IrisUi.ORANGE, colorOfText(payload, "image",
            "Text added after capture: flagged (91%)"));
    }

    @Test
    public void aFaceSwapForcesRedEvenWhenGenaiStaysQuiet() {
        String payload = "{"
            + "\"claims\": [],"
            + "\"image_authenticity_checked\": true,"
            + "\"ai_generated\": {\"status\": \"ok\", \"is_ai_generated\": false,"
            + "\"confidence\": 0.04, \"model\": \"SightEngine\"},"
            + "\"deepfake\": {\"status\": \"ok\", \"is_suspicious\": true,"
            + "\"confidence\": 0.82, \"model\": \"deepfake\"}"
            + "}";

        // The single exception to "only genai sets the colour": a green "No AI detected"
        // beside a live face-swap flag would contradict itself, so the flag takes the
        // headline and the card goes red.
        assertEquals(IrisUi.RED, colorOfText(payload, "image", "Face swap: flagged (82%)"));
    }

    private static List<String> textsForResult(String payload, String inputType) {
        Intent intent = new Intent(RuntimeEnvironment.getApplication(), ResultActivity.class);
        intent.putExtra(ResultActivity.EXTRA_RESPONSE_JSON, payload);
        intent.putExtra(ResultActivity.EXTRA_FALLBACK_TEXT, "");
        intent.putExtra(ResultActivity.EXTRA_INPUT_TYPE, inputType);
        ResultActivity activity = Robolectric
            .buildActivity(ResultActivity.class, intent).setup().get();
        return textsIn(activity.getWindow().getDecorView());
    }

    private static List<String> textsIn(View view) {
        List<String> texts = new ArrayList<>();
        collect(view, texts);
        return texts;
    }

    private static void collect(View view, List<String> texts) {
        if (view instanceof TextView) {
            texts.add(((TextView) view).getText().toString());
        }
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int index = 0; index < group.getChildCount(); index += 1) {
                collect(group.getChildAt(index), texts);
            }
        }
    }

    /**
     * Renders the result and returns the text colour of the first TextView containing
     * the needle. Asserting on the ink rather than the text is the point: the rule under
     * test is which COLOUR a signal earns, and copy alone would pass even if the card
     * around it had been repainted.
     */
    private static int colorOfText(String payload, String inputType, String needle) {
        Intent intent = new Intent(RuntimeEnvironment.getApplication(), ResultActivity.class);
        intent.putExtra(ResultActivity.EXTRA_RESPONSE_JSON, payload);
        intent.putExtra(ResultActivity.EXTRA_FALLBACK_TEXT, "");
        intent.putExtra(ResultActivity.EXTRA_INPUT_TYPE, inputType);
        ResultActivity activity = Robolectric
            .buildActivity(ResultActivity.class, intent).setup().get();

        int[] color = new int[1];
        boolean[] found = new boolean[1];
        findColor(activity.getWindow().getDecorView(), needle, color, found);
        assertTrue("expected a rendered line containing: " + needle, found[0]);
        return color[0];
    }

    private static void findColor(View view, String needle, int[] color, boolean[] found) {
        if (found[0]) return;
        if (view instanceof TextView) {
            TextView text = (TextView) view;
            if (text.getText().toString().contains(needle)) {
                color[0] = text.getTextColors().getDefaultColor();
                found[0] = true;
                return;
            }
        }
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int index = 0; index < group.getChildCount(); index += 1) {
                findColor(group.getChildAt(index), needle, color, found);
            }
        }
    }
}
