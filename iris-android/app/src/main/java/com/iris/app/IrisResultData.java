package com.iris.app;

import android.net.Uri;
import android.text.TextUtils;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

final class IrisResultData {
    // Denominator of the "n of N" pill. Must match len(ALL_SOURCES) in
    // iris-backend/pipeline/sources.py (2 fact-check + 9 news). The backend does not
    // send corroboration.total, so this fallback is what the UI actually renders.
    private static final int APPROVED_SOURCE_TOTAL = 11;

    final List<ClaimItem> claims = new ArrayList<>();
    final List<SkippedSegment> skippedSegments = new ArrayList<>();
    String inputType = "text";
    String ocrText = "";
    // null when the payload carried no detection keys at all (a text check, or a
    // response too degraded to include them), so callers can tell "not an image
    // check" apart from "an image check we could not run".
    ImageAuthenticity imageAuthenticity;
    // Where the shared image came from: the URL Android apps attach to an image
    // share as EXTRA_TEXT. Empty on gallery picks and text checks, which have none.
    String sourceUrl = "";

    private IrisResultData() {}

    static IrisResultData parse(String responseJson, String fallbackText, String inputType) {
        IrisResultData result = new IrisResultData();
        result.inputType = TextUtils.isEmpty(inputType) ? "text" : inputType;

        try {
            JSONObject payload = new JSONObject(responseJson);
            result.ocrText = payload.optString("ocr_text", "");
            result.sourceUrl = payload.optString("source_url", "");
            result.imageAuthenticity = parseImageAuthenticity(payload);
            JSONArray claimArray = payload.optJSONArray("claims");
            JSONArray topLevelSources = firstArray(payload, "evidence_sources", "supporting_sources", "sources");

            if (claimArray == null || claimArray.length() == 0) {
                result.claims.add(parseClaim(payload, fallbackText, topLevelSources, 1));
            } else {
                for (int index = 0; index < claimArray.length(); index += 1) {
                    JSONObject claim = claimArray.optJSONObject(index);
                    if (claim != null) {
                        result.claims.add(parseClaim(claim, fallbackText, topLevelSources, index + 1));
                    }
                }
            }

            result.skippedSegments.addAll(summarizeSkippedSegments(payload.optJSONArray("ignored_segments")));
        } catch (Exception error) {
            ClaimItem item = new ClaimItem();
            item.claimText = TextUtils.isEmpty(fallbackText)
                ? "IRIS returned a result, but Android could not read it cleanly."
                : fallbackText;
            item.verdict = "Not Found";
            item.message = "IRIS returned a result, but Android could not read it cleanly.";
            item.evidenceTotal = APPROVED_SOURCE_TOTAL;
            result.claims.add(item);
        }

        if (result.claims.isEmpty()) {
            ClaimItem item = new ClaimItem();
            item.claimText = TextUtils.isEmpty(fallbackText) ? "No claim text returned." : fallbackText;
            item.verdict = "Not Found";
            item.message = "IRIS did not return a claim result.";
            item.evidenceTotal = APPROVED_SOURCE_TOTAL;
            result.claims.add(item);
        }

        return result;
    }

    /**
     * Maps the backend's image-authenticity payload onto three renderable states.
     *
     * NOT_ASSESSED is the one that matters: it is what we return whenever the check
     * did not run or did not finish, so an unrun check can never be drawn as a
     * cleared image. Confidence rides along only on a positive flag — the backend
     * reports 0.0 whenever nothing was flagged, which means "we did not establish
     * AI-ness", not "we established authenticity", and must not be shown as a score.
     */
    private static ImageAuthenticity parseImageAuthenticity(JSONObject payload) {
        if (!payload.has("ai_generated") && !payload.has("image_authenticity_checked")) {
            return null;
        }

        JSONObject ai = payload.optJSONObject("ai_generated");
        boolean checked = payload.optBoolean("image_authenticity_checked", false);
        String model = ai == null ? "" : ai.optString("model", "");

        // Only a detector that FIRED becomes a flag. With image type out of scope we
        // cannot tell "checked and clear" from "nothing there to check", so a quiet
        // detector stays silent instead of claiming it cleared the image — and the
        // list is dropped entirely for NOT_ASSESSED, which is what the extension does too.
        List<DetectorFlag> flags = new ArrayList<>();
        collectFlag(payload, ImageAuthenticity.FLAG_DEEPFAKE, flags);
        collectFlag(payload, ImageAuthenticity.FLAG_EMBEDDED_TEXT, flags);

        if (!checked || ai == null || !"ok".equals(ai.optString("status", ""))) {
            return new ImageAuthenticity(ImageAuthenticity.NOT_ASSESSED, 0, "");
        }

        if (ai.optBoolean("is_ai_generated", false)) {
            return new ImageAuthenticity(ImageAuthenticity.AI_GENERATED, ai.optDouble("confidence", 0), model, flags);
        }

        return new ImageAuthenticity(ImageAuthenticity.NOT_AI, 0, model, flags);
    }

    /** Adds a detector's reading only when that detector reports `status: ok` and `is_suspicious`. */
    private static void collectFlag(JSONObject payload, String key, List<DetectorFlag> out) {
        JSONObject detector = payload.optJSONObject(key);
        if (detector == null || !"ok".equals(detector.optString("status", ""))) return;
        if (!detector.optBoolean("is_suspicious", false)) return;

        double score = detector.optDouble("confidence", 0);
        if (Double.isNaN(score) || Double.isInfinite(score)) score = 0;
        out.add(new DetectorFlag(key, score));
    }

    /**
     * Pulls the first http(s) URL out of the text a sharing app attached to an image
     * share (EXTRA_TEXT). The share text is often a full caption — "Check this out
     * https://… " — so a plain isEmpty check would throw the link away with the caption,
     * which is exactly the bug this exists to fix. Returns "" when no URL is present:
     * gallery picks share no text at all, and that is a normal case, not an error.
     */
    static String extractSourceUrl(String sharedText) {
        if (TextUtils.isEmpty(sharedText)) return "";

        Matcher matcher = Pattern.compile("https?://\\S+").matcher(sharedText);
        if (!matcher.find()) return "";

        // Captions routinely end a pasted link with sentence punctuation; the trailing
        // dot/paren belongs to the sentence, not the URL.
        String url = matcher.group();
        return url.replaceAll("[.,;:!?)\\]}'\"]+$", "");
    }

    /**
     * Returns the backend response with the shared source URL merged in as source_url,
     * so every surface that later reads this JSON (result screen, history row, history
     * detail) sees the same URL the share carried. A URL that is empty, or a payload
     * that will not parse, passes through untouched: the check itself is the product,
     * and losing an annotation must never cost the user their result.
     */
    static String withSourceUrl(String responseJson, String sourceUrl) {
        if (TextUtils.isEmpty(responseJson) || TextUtils.isEmpty(sourceUrl)) return responseJson;

        try {
            JSONObject payload = new JSONObject(responseJson);
            payload.put("source_url", sourceUrl);
            return payload.toString();
        } catch (Exception error) {
            return responseJson;
        }
    }

    private static ClaimItem parseClaim(JSONObject claim, String fallbackText, JSONArray topLevelSources, int fallbackId) {
        ClaimItem item = new ClaimItem();
        item.claimId = claim.optInt("claim_id", fallbackId);
        item.claimText = firstText(
            claim,
            fallbackText,
            "claim_text",
            "original_text",
            "ocr_text",
            "text"
        );
        item.verdict = firstText(claim, "Not Found", "verdict");
        item.message = firstText(
            claim,
            "IRIS returned this verdict from the backend.",
            "message",
            "verdict_explanation",
            "reason"
        );
        item.politicallySensitive = claim.optBoolean("politically_sensitive", false);
        item.sources = flattenSources(firstArray(claim, "evidence_sources", "supporting_sources", "sources"), topLevelSources);

        JSONObject corroboration = claim.optJSONObject("corroboration");
        int rawCount = claim.optInt("corroboration_count", item.sources.size());
        if (corroboration != null) {
            rawCount = corroboration.optInt("count", rawCount);
            item.evidenceTotal = corroboration.optInt("total", APPROVED_SOURCE_TOTAL);
        } else {
            item.evidenceTotal = APPROVED_SOURCE_TOTAL;
        }

        item.evidenceCount = Math.max(0, Math.min(rawCount, item.sources.size()));
        if (item.evidenceCount == 0 && !item.sources.isEmpty()) {
            item.evidenceCount = item.sources.size();
        }

        return item;
    }

    private static String firstText(JSONObject object, String fallback, String... keys) {
        for (String key : keys) {
            String value = object.optString(key, "");
            if (!TextUtils.isEmpty(value)) return value;
        }
        return fallback == null ? "" : fallback;
    }

    private static JSONArray firstArray(JSONObject object, String... keys) {
        for (String key : keys) {
            JSONArray array = object.optJSONArray(key);
            if (array != null) return array;
        }
        return null;
    }

    private static List<SourceItem> flattenSources(JSONArray rawSources, JSONArray fallbackSources) {
        JSONArray sourceArray = rawSources == null ? fallbackSources : rawSources;
        List<SourceItem> result = new ArrayList<>();
        Set<String> seen = new HashSet<>();
        if (sourceArray == null) return result;

        for (int index = 0; index < sourceArray.length(); index += 1) {
            JSONObject source = sourceArray.optJSONObject(index);
            if (source == null) continue;

            JSONArray nested = source.optJSONArray("articles");
            if (nested != null) {
                for (int nestedIndex = 0; nestedIndex < nested.length(); nestedIndex += 1) {
                    JSONObject article = nested.optJSONObject(nestedIndex);
                    if (article != null) addSource(result, seen, article, source.optString("source", ""));
                }
            } else {
                addSource(result, seen, source, "");
            }
        }

        return result;
    }

    private static void addSource(List<SourceItem> result, Set<String> seen, JSONObject source, String parentOutlet) {
        String status = source.optString("status", "");
        if (!status.isEmpty() && !"extracted".equalsIgnoreCase(status)) return;

        String url = source.optString("url", "").trim();
        if (!isValidHttpUrl(url)) return;

        String key = normalizeUrl(url);
        if (seen.contains(key)) return;
        seen.add(key);

        SourceItem item = new SourceItem();
        item.outlet = firstNonEmpty(source.optString("outlet", ""), source.optString("source", ""), parentOutlet, "Approved source");
        item.date = firstNonEmpty(source.optString("date", ""), source.optString("published_date", ""), "");
        item.title = firstNonEmpty(source.optString("title", ""), url);
        item.url = url;
        result.add(item);
    }

    private static List<SkippedSegment> summarizeSkippedSegments(JSONArray segments) {
        List<SkippedSegment> result = new ArrayList<>();
        if (segments == null) return result;

        Map<String, Integer> counts = new LinkedHashMap<>();
        for (int index = 0; index < segments.length(); index += 1) {
            JSONObject segment = segments.optJSONObject(index);
            if (segment == null) continue;

            String reason = firstNonEmpty(
                segment.optString("reason", ""),
                segment.optString("segment_type", ""),
                "uncheckable"
            );
            String label = skippedLabel(reason);
            int count = Math.max(1, segment.optInt("count", 1));
            counts.put(label, counts.containsKey(label) ? counts.get(label) + count : count);
        }

        for (Map.Entry<String, Integer> entry : counts.entrySet()) {
            result.add(new SkippedSegment(entry.getKey(), entry.getValue()));
        }
        return result;
    }

    private static String skippedLabel(String reason) {
        String normalized = reason == null ? "" : reason.toLowerCase(Locale.ROOT);
        if ("opinion".equals(normalized)) return "opinion";
        if ("recommendation".equals(normalized)) return "recommendation";
        if ("forecast_or_projection".equals(normalized) || "forecast_or_projection_detected".equals(normalized)) return "prediction";
        if ("satire_or_humor".equals(normalized)) return "satire";
        if ("unclear".equals(normalized)) return "unclear segment";
        if ("uncheckable".equals(normalized)) return "uncheckable segment";
        return normalized.replace('_', ' ');
    }

    private static String firstNonEmpty(String... values) {
        for (String value : values) {
            if (value != null && !value.trim().isEmpty()) return value.trim();
        }
        return "";
    }

    private static boolean isValidHttpUrl(String value) {
        try {
            Uri uri = Uri.parse(value);
            return ("http".equals(uri.getScheme()) || "https".equals(uri.getScheme())) && uri.getHost() != null;
        } catch (Exception error) {
            return false;
        }
    }

    private static String normalizeUrl(String value) {
        String normalized = value.toLowerCase(Locale.ROOT);
        int hash = normalized.indexOf('#');
        if (hash >= 0) normalized = normalized.substring(0, hash);
        return normalized.endsWith("/") ? normalized.substring(0, normalized.length() - 1) : normalized;
    }

    static final class ClaimItem {
        int claimId;
        String claimText = "";
        String verdict = "Not Found";
        String message = "";
        boolean politicallySensitive = false;
        int evidenceCount = 0;
        int evidenceTotal = APPROVED_SOURCE_TOTAL;
        List<SourceItem> sources = new ArrayList<>();
    }

    static final class SourceItem {
        String outlet = "Approved source";
        String date = "";
        String title = "";
        String url = "";
    }

    static final class SkippedSegment {
        final String label;
        final int count;

        SkippedSegment(String label, int count) {
            this.label = label;
            this.count = count;
        }
    }

    static final class ImageAuthenticity {
        static final String AI_GENERATED = "ai_generated";
        static final String NOT_AI = "not_ai";
        static final String NOT_ASSESSED = "not_assessed";
        /** Payload key of the face-swap detector, and of the added-text detector. */
        static final String FLAG_DEEPFAKE = "deepfake";
        static final String FLAG_EMBEDDED_TEXT = "embedded_text";

        final String state;
        final double confidence;
        /** The detector that produced the verdict, e.g. "SightEngine"; empty when the payload doesn't say. */
        final String model;
        /** Second detectors that FIRED, each with its own score. Empty is the honest default: a detector that stayed quiet says nothing. */
        final List<DetectorFlag> flags;

        ImageAuthenticity(String state, double confidence, String model) {
            this(state, confidence, model, new ArrayList<DetectorFlag>());
        }

        ImageAuthenticity(String state, double confidence, String model, List<DetectorFlag> flags) {
            this.state = state;
            this.confidence = confidence;
            this.model = model == null ? "" : model;
            this.flags = flags == null ? new ArrayList<DetectorFlag>() : flags;
        }
    }

    /**
     * One secondary detector's own reading. Stored as (kind, score) rather than as
     * rendered copy so the parser stays free of UI text and the renderer can label it
     * in whichever language that screen already speaks. It is an observation of that
     * detector alone — never a vote counted into genai's verdict.
     */
    static final class DetectorFlag {
        /** Payload key the flag came from: {@link ImageAuthenticity#FLAG_DEEPFAKE} or {@link ImageAuthenticity#FLAG_EMBEDDED_TEXT}. */
        final String kind;
        final double confidence;

        DetectorFlag(String kind, double confidence) {
            this.kind = kind;
            this.confidence = confidence;
        }
    }
}
