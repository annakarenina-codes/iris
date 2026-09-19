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

final class IrisResultData {
    private static final int APPROVED_SOURCE_TOTAL = 8;

    final List<ClaimItem> claims = new ArrayList<>();
    final List<SkippedSegment> skippedSegments = new ArrayList<>();
    String inputType = "text";
    String ocrText = "";

    private IrisResultData() {}

    static IrisResultData parse(String responseJson, String fallbackText, String inputType) {
        IrisResultData result = new IrisResultData();
        result.inputType = TextUtils.isEmpty(inputType) ? "text" : inputType;

        try {
            JSONObject payload = new JSONObject(responseJson);
            result.ocrText = payload.optString("ocr_text", "");
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
}
