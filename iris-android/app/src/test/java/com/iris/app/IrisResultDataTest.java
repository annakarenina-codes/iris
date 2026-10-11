package com.iris.app;

import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.Config;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

@RunWith(RobolectricTestRunner.class)
@Config(sdk = 34)
public class IrisResultDataTest {

    @Test
    public void parseReadsSingleClaim() throws Exception {
        JSONObject source = new JSONObject();
        source.put("url", "https://example.com/article1");
        source.put("outlet", "Example News");
        source.put("title", "Example Article");
        source.put("date", "2023-01-01");
        source.put("status", "extracted");

        JSONObject claim = new JSONObject();
        claim.put("claim_text", "Test claim text");
        claim.put("verdict", "Verified");
        claim.put("message", "Explanation");
        claim.put("politically_sensitive", false);
        claim.put("evidence_sources", new JSONArray().put(source));
        claim.put("corroboration", new JSONObject().put("count", 1).put("total", 11));

        JSONObject payload = new JSONObject();
        payload.put("claims", new JSONArray().put(claim));
        payload.put("ignored_segments", new JSONArray());

        IrisResultData result = IrisResultData.parse(payload.toString(), "fallback text", "text");

        assertEquals(1, result.claims.size());
        assertEquals("Test claim text", result.claims.get(0).claimText);
        assertEquals("Verified", result.claims.get(0).verdict);
        assertEquals(1, result.claims.get(0).sources.size());
        assertEquals("https://example.com/article1", result.claims.get(0).sources.get(0).url);
    }

    @Test
    public void parseFallsBackWhenClaimsArrayEmpty() {
        String payload = "{\"claims\": [], \"ignored_segments\": []}";

        IrisResultData result = IrisResultData.parse(payload, "fallback text", "text");

        assertEquals(1, result.claims.size());
        assertEquals("fallback text", result.claims.get(0).claimText);
        assertEquals("Not Found", result.claims.get(0).verdict);
    }

    @Test
    public void parseFallsBackOnMalformedJson() {
        IrisResultData result = IrisResultData.parse("not json", "fallback text", "text");

        assertEquals(1, result.claims.size());
        assertEquals("fallback text", result.claims.get(0).claimText);
        assertEquals("Not Found", result.claims.get(0).verdict);
    }

    @Test
    public void parseGroupsSkippedSegmentsByReason() throws Exception {
        JSONArray segments = new JSONArray();
        segments.put(new JSONObject().put("reason", "opinion").put("count", 3));
        segments.put(new JSONObject().put("reason", "recommendation").put("count", 2));
        segments.put(new JSONObject().put("reason", "opinion").put("count", 1));

        JSONObject payload = new JSONObject();
        payload.put("claims", new JSONArray());
        payload.put("ignored_segments", segments);

        IrisResultData result = IrisResultData.parse(payload.toString(), "fallback", "text");

        assertEquals(2, result.skippedSegments.size());
        assertEquals("opinion", result.skippedSegments.get(0).label);
        assertEquals(4, result.skippedSegments.get(0).count);
        assertEquals("recommendation", result.skippedSegments.get(1).label);
        assertEquals(2, result.skippedSegments.get(1).count);
    }

    @Test
    public void parseDeduplicatesSourcesByUrl() throws Exception {
        JSONObject first = new JSONObject();
        first.put("url", "https://example.com/article/");
        first.put("status", "extracted");

        JSONObject second = new JSONObject();
        second.put("url", "https://example.com/article");
        second.put("status", "extracted");

        JSONObject claim = new JSONObject();
        claim.put("claim_text", "claim");
        claim.put("verdict", "Verified");
        claim.put("evidence_sources", new JSONArray().put(first).put(second));

        JSONObject payload = new JSONObject();
        payload.put("claims", new JSONArray().put(claim));

        IrisResultData result = IrisResultData.parse(payload.toString(), "fallback", "text");

        assertEquals(1, result.claims.get(0).sources.size());
    }

    @Test
    public void parseDropsSourcesWithNonExtractedStatus() throws Exception {
        JSONObject failed = new JSONObject();
        failed.put("url", "https://example.com/article");
        failed.put("status", "failed");

        JSONObject claim = new JSONObject();
        claim.put("claim_text", "claim");
        claim.put("verdict", "Verified");
        claim.put("evidence_sources", new JSONArray().put(failed));

        JSONObject payload = new JSONObject();
        payload.put("claims", new JSONArray().put(claim));

        IrisResultData result = IrisResultData.parse(payload.toString(), "fallback", "text");

        assertTrue(result.claims.get(0).sources.isEmpty());
    }

    @Test
    public void parseDropsSourcesWithInvalidUrl() throws Exception {
        JSONObject bad = new JSONObject();
        bad.put("url", "ftp://example.com/article");
        bad.put("status", "extracted");

        JSONObject claim = new JSONObject();
        claim.put("claim_text", "claim");
        claim.put("verdict", "Verified");
        claim.put("evidence_sources", new JSONArray().put(bad));

        JSONObject payload = new JSONObject();
        payload.put("claims", new JSONArray().put(claim));

        IrisResultData result = IrisResultData.parse(payload.toString(), "fallback", "text");

        assertTrue(result.claims.get(0).sources.isEmpty());
    }

    @Test
    public void parseKeepsPoliticallySensitiveFlag() throws Exception {
        JSONObject claim = new JSONObject();
        claim.put("claim_text", "claim");
        claim.put("verdict", "Refuted");
        claim.put("politically_sensitive", true);

        JSONObject payload = new JSONObject();
        payload.put("claims", new JSONArray().put(claim));

        IrisResultData result = IrisResultData.parse(payload.toString(), "fallback", "text");

        assertTrue(result.claims.get(0).politicallySensitive);
    }

    @Test
    public void parseClampsEvidenceCountToAvailableSources() throws Exception {
        JSONObject source = new JSONObject();
        source.put("url", "https://example.com/one");
        source.put("status", "extracted");

        JSONObject claim = new JSONObject();
        claim.put("claim_text", "claim");
        claim.put("verdict", "Verified");
        claim.put("evidence_sources", new JSONArray().put(source));
        claim.put("corroboration", new JSONObject().put("count", 9).put("total", 11));

        JSONObject payload = new JSONObject();
        payload.put("claims", new JSONArray().put(claim));

        IrisResultData result = IrisResultData.parse(payload.toString(), "fallback", "text");

        assertEquals(1, result.claims.get(0).evidenceCount);
        assertEquals(11, result.claims.get(0).evidenceTotal);
    }

    @Test
    public void parseFlattensNestedArticleArrays() throws Exception {
        JSONObject article = new JSONObject();
        article.put("url", "https://example.com/nested");
        article.put("status", "extracted");

        JSONObject outlet = new JSONObject();
        outlet.put("source", "Nested Outlet");
        outlet.put("articles", new JSONArray().put(article));

        JSONObject claim = new JSONObject();
        claim.put("claim_text", "claim");
        claim.put("verdict", "Verified");
        claim.put("evidence_sources", new JSONArray().put(outlet));

        JSONObject payload = new JSONObject();
        payload.put("claims", new JSONArray().put(claim));

        IrisResultData result = IrisResultData.parse(payload.toString(), "fallback", "text");

        assertEquals(1, result.claims.get(0).sources.size());
        assertEquals("https://example.com/nested", result.claims.get(0).sources.get(0).url);
    }

    @Test
    public void parseUsesTopLevelSourcesWhenClaimHasNone() throws Exception {
        JSONObject source = new JSONObject();
        source.put("url", "https://example.com/top-level");
        source.put("status", "extracted");

        JSONObject claim = new JSONObject();
        claim.put("claim_text", "claim");
        claim.put("verdict", "Verified");

        JSONObject payload = new JSONObject();
        payload.put("claims", new JSONArray().put(claim));
        payload.put("evidence_sources", new JSONArray().put(source));

        IrisResultData result = IrisResultData.parse(payload.toString(), "fallback", "text");

        assertEquals(1, result.claims.get(0).sources.size());
        assertEquals("https://example.com/top-level", result.claims.get(0).sources.get(0).url);
    }

    @Test
    public void parseKeepsProvidedInputType() {
        String payload = "{\"claims\": []}";

        IrisResultData result = IrisResultData.parse(payload, "fallback", "image");

        assertEquals("image", result.inputType);
    }

    @Test
    public void parseDefaultsEmptyInputTypeToText() {
        String payload = "{\"claims\": []}";

        IrisResultData result = IrisResultData.parse(payload, "fallback", "");

        assertEquals("text", result.inputType);
    }

    @Test
    public void imageAuthenticityIsNullWhenPayloadCarriesNoDetectionKeys() {
        IrisResultData result = IrisResultData.parse("{\"claims\": []}", "fallback", "text");

        assertNull(result.imageAuthenticity);
    }

    @Test
    public void imageAuthenticityFlagsConfirmedDetectionWithScore() {
        String payload = "{"
            + "\"claims\": [],"
            + "\"image_authenticity_checked\": true,"
            + "\"ai_generated\": {\"status\": \"ok\", \"is_ai_generated\": true, \"confidence\": 0.529}"
            + "}";

        IrisResultData result = IrisResultData.parse(payload, "fallback", "image");

        assertEquals(IrisResultData.ImageAuthenticity.AI_GENERATED, result.imageAuthenticity.state);
        assertEquals(0.529, result.imageAuthenticity.confidence, 0.0001);
    }

    @Test
    public void imageAuthenticityReportsClearResultWithoutPublishingAScore() {
        String payload = "{"
            + "\"claims\": [],"
            + "\"image_authenticity_checked\": true,"
            + "\"ai_generated\": {\"status\": \"ok\", \"is_ai_generated\": false, \"confidence\": 0.0}"
            + "}";

        IrisResultData result = IrisResultData.parse(payload, "fallback", "image");

        assertEquals(IrisResultData.ImageAuthenticity.NOT_AI, result.imageAuthenticity.state);
        // A clear result must not carry a confidence the UI could render as
        // "how sure we are it is real" — the backend's 0.0 only means no flag.
        assertEquals(0.0, result.imageAuthenticity.confidence, 0.0);
    }

    @Test
    public void imageAuthenticityReportsNotAssessedWhenDetectionNeverRan() {
        String payload = "{\"claims\": [], \"image_authenticity_checked\": false}";

        IrisResultData result = IrisResultData.parse(payload, "fallback", "image");

        assertEquals(IrisResultData.ImageAuthenticity.NOT_ASSESSED, result.imageAuthenticity.state);
    }

    @Test
    public void imageAuthenticityReportsNotAssessedWhenModelsFailedToLoad() {
        String payload = "{"
            + "\"claims\": [],"
            + "\"image_authenticity_checked\": false,"
            + "\"ai_generated\": {\"status\": \"model_unavailable\", \"is_ai_generated\": false}"
            + "}";

        IrisResultData result = IrisResultData.parse(payload, "fallback", "image");

        assertEquals(IrisResultData.ImageAuthenticity.NOT_ASSESSED, result.imageAuthenticity.state);
    }

    @Test
    public void imageAuthenticityReportsNotAssessedOnDegradedDetectionStatus() {
        String payload = "{"
            + "\"claims\": [],"
            + "\"image_authenticity_checked\": true,"
            + "\"ai_generated\": {\"status\": \"error\", \"is_ai_generated\": false}"
            + "}";

        IrisResultData result = IrisResultData.parse(payload, "fallback", "image");

        assertEquals(IrisResultData.ImageAuthenticity.NOT_ASSESSED, result.imageAuthenticity.state);
    }

    @Test
    public void imageAuthenticityCarriesTheDetectorModelName() {
        String payload = "{"
            + "\"claims\": [],"
            + "\"image_authenticity_checked\": true,"
            + "\"ai_generated\": {\"status\": \"ok\", \"is_ai_generated\": true,"
            + "\"confidence\": 0.99, \"model\": \"SightEngine\"}"
            + "}";

        IrisResultData result = IrisResultData.parse(payload, "fallback", "image");

        assertEquals("SightEngine", result.imageAuthenticity.model);
    }

    @Test
    public void imageAuthenticityModelIsEmptyWhenThePayloadDoesNotSay() {
        String payload = "{"
            + "\"claims\": [],"
            + "\"image_authenticity_checked\": true,"
            + "\"ai_generated\": {\"status\": \"ok\", \"is_ai_generated\": false, \"confidence\": 0.0}"
            + "}";

        IrisResultData result = IrisResultData.parse(payload, "fallback", "image");

        assertEquals("", result.imageAuthenticity.model);
    }

    @Test
    public void imageAuthenticityCarriesAFiredDeepfakeFlag() {
        String payload = "{"
            + "\"claims\": [],"
            + "\"image_authenticity_checked\": true,"
            + "\"ai_generated\": {\"status\": \"ok\", \"is_ai_generated\": true, \"confidence\": 0.9},"
            + "\"deepfake\": {\"status\": \"ok\", \"is_suspicious\": true, \"confidence\": 0.82},"
            + "\"embedded_text\": {\"status\": \"ok\", \"is_suspicious\": false, \"confidence\": 0.01}"
            + "}";

        IrisResultData result = IrisResultData.parse(payload, "fallback", "image");

        // Only the detector that fired becomes a flag, and it keeps its own score:
        // a quiet embedded-text detector contributes nothing at all.
        assertEquals(1, result.imageAuthenticity.flags.size());
        assertEquals(IrisResultData.ImageAuthenticity.FLAG_DEEPFAKE,
            result.imageAuthenticity.flags.get(0).kind);
        assertEquals(0.82, result.imageAuthenticity.flags.get(0).confidence, 0.0001);
    }

    @Test
    public void imageAuthenticityStaysSilentWhenNoDetectorFired() {
        String payload = "{"
            + "\"claims\": [],"
            + "\"image_authenticity_checked\": true,"
            + "\"ai_generated\": {\"status\": \"ok\", \"is_ai_generated\": false, \"confidence\": 0.0},"
            + "\"deepfake\": {\"status\": \"ok\", \"is_suspicious\": false, \"confidence\": 0.01},"
            + "\"embedded_text\": {\"status\": \"error\", \"error\": \"quota\"}"
            + "}";

        IrisResultData result = IrisResultData.parse(payload, "fallback", "image");

        // A quiet or failed detector must not grow into a "checked and clear" claim the
        // payload never made: empty is the only honest reading of what it did not say.
        assertEquals(IrisResultData.ImageAuthenticity.NOT_AI, result.imageAuthenticity.state);
        assertEquals(0, result.imageAuthenticity.flags.size());
    }

    @Test
    public void imageAuthenticityKeepsAFiredFlagEvenWhenGenaiStaysQuiet() {
        String payload = "{"
            + "\"claims\": [],"
            + "\"image_authenticity_checked\": true,"
            + "\"ai_generated\": {\"status\": \"ok\", \"is_ai_generated\": false, \"confidence\": 0.04},"
            + "\"deepfake\": {\"status\": \"ok\", \"is_suspicious\": true, \"confidence\": 0.82}"
            + "}";

        IrisResultData result = IrisResultData.parse(payload, "fallback", "image");

        // Each detector reports only what it saw: genai's state is untouched by a flag
        // from a different detector, and the renderer decides how to show both together.
        assertEquals(IrisResultData.ImageAuthenticity.NOT_AI, result.imageAuthenticity.state);
        assertEquals(0.0, result.imageAuthenticity.confidence, 0.0);
        assertEquals(1, result.imageAuthenticity.flags.size());
        assertEquals(IrisResultData.ImageAuthenticity.FLAG_DEEPFAKE,
            result.imageAuthenticity.flags.get(0).kind);
    }

    @Test
    public void imageAuthenticityDropsFlagsWhenTheCheckNeverRan() {
        String payload = "{"
            + "\"claims\": [],"
            + "\"image_authenticity_checked\": false,"
            + "\"deepfake\": {\"status\": \"ok\", \"is_suspicious\": true, \"confidence\": 0.82}"
            + "}";

        IrisResultData result = IrisResultData.parse(payload, "fallback", "image");

        assertEquals(IrisResultData.ImageAuthenticity.NOT_ASSESSED, result.imageAuthenticity.state);
        assertEquals(0, result.imageAuthenticity.flags.size());
    }

    @Test
    public void extractSourceUrlFindsBareUrlInCaption() {
        String caption = "https://www.example.com/post/123";

        assertEquals("https://www.example.com/post/123",
            IrisResultData.extractSourceUrl(caption));
    }

    @Test
    public void extractSourceUrlFindsUrlInsideCaptionText() {
        String caption = "Check this out https://www.example.com/post?id=1 before it drops!";

        assertEquals("https://www.example.com/post?id=1",
            IrisResultData.extractSourceUrl(caption));
    }

    @Test
    public void extractSourceUrlStripsSentencePunctuation() {
        String caption = "Wild photo. See https://www.example.com/photo.";

        assertEquals("https://www.example.com/photo",
            IrisResultData.extractSourceUrl(caption));
    }

    @Test
    public void extractSourceUrlReturnsEmptyWithoutUrl() {
        assertEquals("", IrisResultData.extractSourceUrl("just a caption, no link"));
        assertEquals("", IrisResultData.extractSourceUrl(""));
        assertEquals("", IrisResultData.extractSourceUrl(null));
    }

    @Test
    public void withSourceUrlMergesUrlIntoPayload() throws Exception {
        String payload = "{\"claims\": [], \"verdict\": \"Verified\"}";

        String merged = IrisResultData.withSourceUrl(payload, "https://www.example.com/post");

        assertEquals("https://www.example.com/post",
            new JSONObject(merged).getString("source_url"));
        // The check's own fields survive the merge untouched.
        assertEquals("Verified", new JSONObject(merged).getString("verdict"));
    }

    @Test
    public void withSourceUrlPassesPayloadThroughWhenUrlMissing() {
        String payload = "{\"claims\": []}";

        assertEquals(payload, IrisResultData.withSourceUrl(payload, ""));
        assertEquals(payload, IrisResultData.withSourceUrl(payload, null));
    }

    @Test
    public void withSourceUrlNeverDropsTheResultOnBadJson() {
        assertEquals("not json", IrisResultData.withSourceUrl("not json", "https://x.example/a"));
        assertEquals("", IrisResultData.withSourceUrl("", "https://x.example/a"));
    }

    @Test
    public void parseReadsMergedSourceUrl() throws Exception {
        JSONObject payload = new JSONObject();
        payload.put("claims", new JSONArray());
        payload.put("source_url", "https://www.example.com/post");

        IrisResultData result = IrisResultData.parse(payload.toString(), "fallback", "image");

        assertEquals("https://www.example.com/post", result.sourceUrl);
    }

    @Test
    public void parseSourceUrlDefaultsToEmptyOnTextChecks() {
        IrisResultData result = IrisResultData.parse(
            "{\"claims\": [], \"ignored_segments\": []}", "fallback", "text");

        assertEquals("", result.sourceUrl);
    }
}
