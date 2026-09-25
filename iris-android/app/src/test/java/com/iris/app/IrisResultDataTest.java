package com.iris.app;

import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.Config;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
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
}
