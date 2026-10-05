package com.iris.app;

import android.util.Base64;

import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.Config;

import java.nio.charset.StandardCharsets;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

/**
 * Pins the bring-your-own-key SightEngine call to the extension's contract
 * (iris-extension/src/background.js analyzeImageAuthenticitySightEngine): every branch
 * reachable without a live network round trip. The check() paths exercised here return
 * before opening a connection — a unit test must never spend real quota.
 */
@RunWith(RobolectricTestRunner.class)
@Config(sdk = 34)
public class SightEngineAuthenticityTest {

    // --- check() guards: both fail before any socket is opened. ---

    @Test
    public void missingCredentialsFailWithoutTouchingTheNetwork() {
        JSONObject missingUser = SightEngineAuthenticity.check("", "secret", new byte[] {1});
        assertFalse(missingUser.optBoolean("image_authenticity_checked", true));
        assertEquals("SightEngine credentials not configured.",
            missingUser.optJSONObject("ai_generated").optString("error"));

        JSONObject missingSecret = SightEngineAuthenticity.check("user", null, new byte[] {1});
        assertFalse(missingSecret.optBoolean("image_authenticity_checked", true));
        assertEquals("SightEngine credentials not configured.",
            missingSecret.optJSONObject("ai_generated").optString("error"));
    }

    @Test
    public void configuredCredentialsWithNoImageStillFailFast() {
        JSONObject result = SightEngineAuthenticity.check("user", "secret", new byte[0]);

        assertFalse(result.optBoolean("image_authenticity_checked", true));
        assertEquals("No image was sent to SightEngine.",
            result.optJSONObject("ai_generated").optString("error"));
    }

    // --- parseVerdict: the two probability shapes and the threshold. ---

    @Test
    public void plainNumberProbabilityIsReadDirectly() throws Exception {
        JSONObject verdict = SightEngineAuthenticity.parseVerdict(200, "{\"type\": 0.7}");

        assertTrue(verdict.getBoolean("image_authenticity_checked"));
        JSONObject ai = verdict.getJSONObject("ai_generated");
        assertEquals(0.7, ai.getDouble("suspicion_score"), 0.0001);
        assertEquals(0.7, ai.getDouble("confidence"), 0.0001);
        assertTrue(ai.getBoolean("is_suspicious"));
        assertTrue(ai.getBoolean("is_ai_generated"));
        assertEquals("SightEngine", ai.getString("model"));
        assertEquals("ok", ai.getString("status"));
        assertTrue("a clean verdict carries no error", ai.isNull("error"));
    }

    @Test
    public void objectProbabilityIsReadFromAiGenerated() throws Exception {
        JSONObject verdict = SightEngineAuthenticity.parseVerdict(
            200, "{\"type\": {\"ai_generated\": 0.99}}");

        assertEquals(0.99, verdict.getJSONObject("ai_generated").getDouble("suspicion_score"), 0.0001);
        assertTrue(verdict.getJSONObject("ai_generated").getBoolean("is_suspicious"));
    }

    @Test
    public void objectProbabilityFallsBackToProbabilityKey() throws Exception {
        JSONObject verdict = SightEngineAuthenticity.parseVerdict(
            200, "{\"type\": {\"probability\": 0.4}}");

        assertEquals(0.4, verdict.getJSONObject("ai_generated").getDouble("suspicion_score"), 0.0001);
        assertFalse("0.4 is under the 0.5 threshold", verdict.getJSONObject("ai_generated").getBoolean("is_suspicious"));
    }

    @Test
    public void theThresholdIsStrictlyAboveHalf() throws Exception {
        JSONObject exactlyHalf = SightEngineAuthenticity.parseVerdict(200, "{\"type\": 0.5}");
        assertFalse("0.5 itself must not trip the badge",
            exactlyHalf.getJSONObject("ai_generated").getBoolean("is_suspicious"));

        JSONObject justOver = SightEngineAuthenticity.parseVerdict(200, "{\"type\": 0.51}");
        assertTrue(justOver.getJSONObject("ai_generated").getBoolean("is_suspicious"));
    }

    @Test
    public void unparseableProbabilitiesReadAsZeroNotAsAVerdict() throws Exception {
        JSONObject objectWithoutKeys = SightEngineAuthenticity.parseVerdict(
            200, "{\"type\": {\"something_else\": 1}}");
        assertFalse(objectWithoutKeys.getJSONObject("ai_generated").getBoolean("is_suspicious"));
        assertEquals(0.0, objectWithoutKeys.getJSONObject("ai_generated").getDouble("suspicion_score"), 0.0001);

        JSONObject unparseableString = SightEngineAuthenticity.parseVerdict(
            200, "{\"type\": \"not-a-number\"}");
        assertEquals(0.0, unparseableString.getJSONObject("ai_generated").getDouble("suspicion_score"), 0.0001);

        JSONObject noTypeAtAll = SightEngineAuthenticity.parseVerdict(200, "{}");
        assertEquals(0.0, noTypeAtAll.getJSONObject("ai_generated").getDouble("suspicion_score"), 0.0001);
        assertTrue(noTypeAtAll.getBoolean("image_authenticity_checked"));
    }

    @Test
    public void stringProbabilityIsParsedAsANumber() throws Exception {
        JSONObject verdict = SightEngineAuthenticity.parseVerdict(200, "{\"type\": \"0.6\"}");

        assertEquals(0.6, verdict.getJSONObject("ai_generated").getDouble("suspicion_score"), 0.0001);
        assertTrue(verdict.getJSONObject("ai_generated").getBoolean("is_suspicious"));
    }

    // --- parseVerdict: honest failures, one shape per cause. ---

    @Test
    public void aNonJsonSuccessBodyFailsAsNonJson() throws Exception {
        JSONObject result = SightEngineAuthenticity.parseVerdict(200, "not json at all");

        assertFalse(result.getBoolean("image_authenticity_checked"));
        assertEquals("SightEngine returned non-JSON response.",
            result.getJSONObject("ai_generated").optString("error"));
    }

    @Test
    public void anHttpErrorCarriesTheApisOwnMessage() throws Exception {
        JSONObject result = SightEngineAuthenticity.parseVerdict(
            400, "{\"message\": \"No media sent\"}");

        assertFalse(result.getBoolean("image_authenticity_checked"));
        assertEquals("No media sent", result.getJSONObject("ai_generated").optString("error"));
    }

    @Test
    public void anHttpErrorWithoutAMessageNamesTheStatus() throws Exception {
        JSONObject result = SightEngineAuthenticity.parseVerdict(500, "{}");

        assertFalse(result.getBoolean("image_authenticity_checked"));
        assertEquals("SightEngine HTTP 500", result.getJSONObject("ai_generated").optString("error"));
    }

    @Test
    public void anHtmlErrorPageNamesTheStatusRatherThanClaimingANonJsonSuccess() throws Exception {
        // A dead proxy answers with HTML, not JSON: the status is the real story here.
        JSONObject result = SightEngineAuthenticity.parseVerdict(503, "<html>bad gateway</html>");

        assertFalse(result.getBoolean("image_authenticity_checked"));
        assertEquals("SightEngine HTTP 503", result.getJSONObject("ai_generated").optString("error"));
    }

    // --- mergeInto: the backend's own verdict always wins. ---

    @Test
    public void mergeFillsABackendThatCarriedNoVerdict() throws Exception {
        String merged = SightEngineAuthenticity.mergeInto(
            "{\"claims\": [], \"message\": \"ok\"}",
            SightEngineAuthenticity.parseVerdict(200, "{\"type\": 0.9}"));

        JSONObject payload = new JSONObject(merged);
        assertTrue(payload.getBoolean("image_authenticity_checked"));
        assertEquals(0.9, payload.getJSONObject("ai_generated").getDouble("suspicion_score"), 0.0001);
        assertTrue("the claims half must survive the merge", payload.has("claims"));
    }

    @Test
    public void mergeLeavesTheBackendsOwnVerdictUntouched() {
        String backend = "{\"image_authenticity_checked\": true, "
            + "\"ai_generated\": {\"status\": \"ok\", \"model\": \"something-else\"}}";

        String merged = SightEngineAuthenticity.mergeInto(backend,
            SightEngineAuthenticity.parseVerdict(200, "{\"type\": 0.9}"));

        assertEquals("two verdicts for one image must never fight", backend, merged);
    }

    @Test
    public void mergeKeepsABackendFailureItRanItself() {
        String backend = "{\"image_authenticity_checked\": false, "
            + "\"ai_generated\": {\"status\": \"error\", \"error\": \"backend creds\"}}";

        String merged = SightEngineAuthenticity.mergeInto(backend,
            SightEngineAuthenticity.parseVerdict(200, "{\"type\": 0.9}"));

        assertEquals("the backend ran its own check; its honest failure ships", backend, merged);
    }

    @Test
    public void mergeIgnoresNullVerdictsAndUnparseablePayloads() {
        String response = "{\"claims\": []}";
        assertEquals(response, SightEngineAuthenticity.mergeInto(response, null));
        assertEquals("not json", SightEngineAuthenticity.mergeInto("not json",
            SightEngineAuthenticity.parseVerdict(200, "{\"type\": 0.9}")));
    }

    // --- payloadWithClaimError: a dead claims half still shows the badge. ---

    @Test
    public void deadClaimsBackendStillDeliversTheSurvivingVerdict() throws Exception {
        String payload = SightEngineAuthenticity.payloadWithClaimError(
            "IRIS could not reach the server.",
            SightEngineAuthenticity.parseVerdict(200, "{\"type\": 0.9}"));

        JSONObject json = new JSONObject(payload);
        assertEquals("IRIS could not reach the server.", json.getString("message"));
        assertTrue(json.getBoolean("image_authenticity_checked"));
        assertEquals(0.9, json.getJSONObject("ai_generated").getDouble("suspicion_score"), 0.0001);
    }

    @Test
    public void anEmptyClaimErrorFallsBackToTheGenericMessage() throws Exception {
        String payload = SightEngineAuthenticity.payloadWithClaimError("",
            SightEngineAuthenticity.parseVerdict(200, "{\"type\": 0.1}"));

        assertEquals("IRIS could not verify the selected image.",
            new JSONObject(payload).getString("message"));
    }

    @Test
    public void payloadWithoutAVerdictStaysCheckedFalse() throws Exception {
        String payload = SightEngineAuthenticity.payloadWithClaimError(
            "IRIS could not reach the server.", null);

        JSONObject json = new JSONObject(payload);
        assertEquals("IRIS could not reach the server.", json.getString("message"));
        assertFalse(json.getBoolean("image_authenticity_checked"));
        assertNull("no verdict half means no verdict object", json.optJSONObject("ai_generated"));
    }

    // --- bytesFromDataUrl ---

    @Test
    public void aDataUrlDecodesBackToItsBytes() {
        byte[] original = "hello sightengine".getBytes(StandardCharsets.UTF_8);
        String dataUrl = "data:image/png;base64," + Base64.encodeToString(original, Base64.NO_WRAP);

        assertArrayEquals(original, SightEngineAuthenticity.bytesFromDataUrl(dataUrl));
    }

    @Test
    public void malformedDataUrlsYieldNoBytesRatherThanAnException() {
        assertArrayEquals(new byte[0], SightEngineAuthenticity.bytesFromDataUrl(null));
        assertArrayEquals(new byte[0], SightEngineAuthenticity.bytesFromDataUrl("no-comma-here"));
        assertArrayEquals(new byte[0], SightEngineAuthenticity.bytesFromDataUrl("data:image/png;base64"));
        assertArrayEquals(new byte[0], SightEngineAuthenticity.bytesFromDataUrl("data:image/png;base64,%%%"));
    }

    // --- failure: the one honest shape every surface renders as Not assessed. ---

    @Test
    public void failureAlwaysCarriesCheckedFalseAndAnError() throws Exception {
        JSONObject result = SightEngineAuthenticity.failure(null);

        assertFalse(result.getBoolean("image_authenticity_checked"));
        JSONObject ai = result.getJSONObject("ai_generated");
        assertEquals("error", ai.getString("status"));
        assertEquals("SightEngine request failed.", ai.getString("error"));
    }

    // --- deepfake and embedded text: independent observations, never a fusion. ---

    @Test
    public void eachDetectorReportsOnlyItsOwnReading() throws Exception {
        String body = "{\"type\": {\"ai_generated\": 0.001, \"deepfake\": 0.82},"
            + " \"text\": {\"has_artificial\": 0.91, \"has_natural\": 0.05}}";
        JSONObject verdict = SightEngineAuthenticity.parseVerdict(200, body);

        // Three verdicts, no fusion: a deepfake flag must not drag genai up with it.
        JSONObject ai = verdict.getJSONObject("ai_generated");
        assertFalse(ai.getBoolean("is_suspicious"));
        assertEquals(0.001, ai.getDouble("suspicion_score"), 0.0001);

        JSONObject deepfake = verdict.getJSONObject("deepfake");
        assertTrue(deepfake.getBoolean("is_suspicious"));
        assertTrue(deepfake.getBoolean("is_deepfake"));
        assertEquals(0.82, deepfake.getDouble("suspicion_score"), 0.0001);

        JSONObject embedded = verdict.getJSONObject("embedded_text");
        assertTrue(embedded.getBoolean("is_suspicious"));
        assertEquals(0.91, embedded.getDouble("has_artificial"), 0.0001);
        assertEquals(0.05, embedded.getDouble("has_natural"), 0.0001);
    }

    @Test
    public void detectorAtExactlyHalfStaysNotSuspicious() throws Exception {
        // Same strictly-greater-than-0.5 rule as ai_generated: the backend, the
        // extension and this app can never disagree about the same image.
        String body = "{\"type\": {\"ai_generated\": 0.1, \"deepfake\": 0.5},"
            + " \"text\": {\"has_artificial\": 0.5, \"has_natural\": 0.5}}";
        JSONObject verdict = SightEngineAuthenticity.parseVerdict(200, body);

        assertFalse(verdict.getJSONObject("deepfake").getBoolean("is_suspicious"));
        assertFalse(verdict.getJSONObject("embedded_text").getBoolean("is_suspicious"));
    }

    @Test
    public void textInTheSceneIsNotAnAccusation() throws Exception {
        // A storefront sign is natural text. Only text added after the shot is flagged.
        String body = "{\"type\": {\"ai_generated\": 0.1},"
            + " \"text\": {\"has_artificial\": 0.001, \"has_natural\": 0.93}}";
        JSONObject verdict = SightEngineAuthenticity.parseVerdict(200, body);

        JSONObject embedded = verdict.getJSONObject("embedded_text");
        assertFalse(embedded.getBoolean("is_suspicious"));
        assertEquals(0.93, embedded.getDouble("has_natural"), 0.0001);
        assertEquals(0.001, embedded.getDouble("has_artificial"), 0.0001);
    }

    @Test
    public void missingDetectorKeysStillYieldAFullObservation() throws Exception {
        JSONObject verdict = SightEngineAuthenticity.parseVerdict(
            200, "{\"type\": {\"ai_generated\": 0.9}}");

        JSONObject deepfake = verdict.getJSONObject("deepfake");
        assertFalse(deepfake.getBoolean("is_suspicious"));
        assertEquals(0.0, deepfake.getDouble("suspicion_score"), 0.0001);
        assertEquals("SightEngine", deepfake.getString("model"));

        JSONObject embedded = verdict.getJSONObject("embedded_text");
        assertFalse(embedded.getBoolean("is_suspicious"));
        assertEquals(0.0, embedded.getDouble("has_natural"), 0.0001);
    }

    @Test
    public void mergeCarriesTheExtraDetectors() throws Exception {
        JSONObject authenticity = SightEngineAuthenticity.parseVerdict(200,
            "{\"type\": {\"ai_generated\": 0.9, \"deepfake\": 0.7},"
                + " \"text\": {\"has_artificial\": 0.6, \"has_natural\": 0.2}}");

        JSONObject json = new JSONObject(
            SightEngineAuthenticity.mergeInto("{\"claims\": []}", authenticity));

        assertTrue(json.getBoolean("image_authenticity_checked"));
        assertEquals(0.7, json.getJSONObject("deepfake").getDouble("suspicion_score"), 0.0001);
        assertEquals(0.6, json.getJSONObject("embedded_text").getDouble("has_artificial"), 0.0001);
    }

    @Test
    public void claimErrorPayloadCarriesTheExtraDetectors() throws Exception {
        JSONObject authenticity = SightEngineAuthenticity.parseVerdict(200,
            "{\"type\": {\"ai_generated\": 0.1, \"deepfake\": 0.4},"
                + " \"text\": {\"has_artificial\": 0.3, \"has_natural\": 0.8}}");

        JSONObject json = new JSONObject(SightEngineAuthenticity.payloadWithClaimError(
            "backend down", authenticity));

        assertEquals("backend down", json.getString("message"));
        assertTrue(json.getBoolean("image_authenticity_checked"));
        assertEquals(0.4, json.getJSONObject("deepfake").getDouble("suspicion_score"), 0.0001);
        assertEquals(0.8, json.getJSONObject("embedded_text").getDouble("has_natural"), 0.0001);
    }

    @Test
    public void aFailureGrowsNoExtraDetectorVerdicts() throws Exception {
        JSONObject result = SightEngineAuthenticity.failure("quota exceeded");

        assertFalse("absent stays absent", result.has("deepfake"));
        assertFalse("absent stays absent", result.has("embedded_text"));
    }
}
