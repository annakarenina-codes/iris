package com.iris.app;

import android.content.Context;
import android.util.Base64;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/**
 * The authenticity half of an image check, asked of SightEngine directly from this app —
 * the same bring-your-own-key call the extension runs in its own worker
 * (iris-extension/src/background.js analyzeImageAuthenticitySightEngine).
 *
 * It never throws: an unassessed image is an honest result every surface already knows how
 * to render, so every failure collapses into {image_authenticity_checked: false}. The
 * credentials come from the in-app settings card, never from code — this repository and
 * this APK are both public, and a key shipped inside either is a key anyone can spend.
 */
final class SightEngineAuthenticity {
    private static final String API_URL = "https://api.sightengine.com/1.0/check.json";
    // Mirrors the extension's SIGHTENGINE_TIMEOUT_MS deadline for the response wait.
    // HttpURLConnection splits that across connect and read, since it cannot cap the total.
    private static final int CONNECT_TIMEOUT_MS = 10000;
    private static final int READ_TIMEOUT_MS = 30000;

    private SightEngineAuthenticity() {}

    static JSONObject check(Context context, byte[] imageBytes) {
        return check(
            IrisPrefs.getSightengineApiUser(context),
            IrisPrefs.getSightengineApiSecret(context),
            imageBytes
        );
    }

    /**
     * Runs the check, or answers the honest failure shape without touching the network.
     *
     * Package-visible with explicit credentials so tests can pin every branch that does
     * not require a live call.
     */
    static JSONObject check(String apiUser, String apiSecret, byte[] imageBytes) {
        String user = apiUser == null ? "" : apiUser.trim();
        String secret = apiSecret == null ? "" : apiSecret.trim();
        if (user.isEmpty() || secret.isEmpty()) {
            return failure("SightEngine credentials not configured.");
        }
        if (imageBytes == null || imageBytes.length == 0) {
            return failure("No image was sent to SightEngine.");
        }

        HttpURLConnection connection = null;
        try {
            connection = (HttpURLConnection) new URL(API_URL).openConnection();
            connection.setRequestMethod("POST");
            connection.setConnectTimeout(CONNECT_TIMEOUT_MS);
            connection.setReadTimeout(READ_TIMEOUT_MS);
            connection.setDoOutput(true);

            String boundary = "IRIS" + System.currentTimeMillis();
            connection.setRequestProperty("Content-Type", "multipart/form-data; boundary=" + boundary);
            try (OutputStream output = connection.getOutputStream()) {
                // SightEngine only reads `media` as a file part: a bare string field comes
                // back as HTTP 400 code 1042 "No media sent" — the same shape the extension
                // documents at background.js:449-451.
                // Deepfake and embedded text ride the same request as genai: one call, one
                // process batch, and the same strictly-greater-than-0.5 rule the backend and
                // the extension use so every surface agrees about the same image.
                writeField(output, boundary, "models", "genai,deepfake,text");
                writeField(output, boundary, "api_user", user);
                writeField(output, boundary, "api_secret", secret);
                writeMedia(output, boundary, imageBytes);
            }

            int status = connection.getResponseCode();
            InputStream inputStream = status >= 200 && status < 300
                ? connection.getInputStream()
                : connection.getErrorStream();
            String body = readStream(inputStream);
            return parseVerdict(status, body);
        } catch (Exception error) {
            String message = error.getMessage();
            return failure(message == null || message.isEmpty()
                ? "SightEngine request failed." : message);
        } finally {
            if (connection != null) connection.disconnect();
        }
    }

    /**
     * Maps one SightEngine HTTP answer onto the verdict shape every IRIS surface reads.
     *
     * The `type` probability ships as a plain number and as an object such as
     * {ai_generated: 0.99}: read both shapes, and read anything unparseable as 0 rather
     * than as a verdict (extension parity, background.js:498-508).
     */
    static JSONObject parseVerdict(int status, String body) {
        JSONObject data = null;
        boolean json = true;
        try {
            data = new JSONObject(body == null ? "" : body);
        } catch (Exception error) {
            json = false;
        }

        // The status decides first: a proxy that answers a failed call with an HTML
        // error page is not a "non-JSON response" failure — the extension names the
        // status itself in that case (background.js:465-470).
        if (status < 200 || status >= 300) {
            String message = json ? data.optString("message", "") : "";
            return failure(message.isEmpty() ? "SightEngine HTTP " + status : message);
        }
        if (!json) {
            return failure("SightEngine returned non-JSON response.");
        }

        double probability = probabilityOf(data);
        boolean suspicious = probability > 0.5;

        // Deepfake and embedded text live in their own sub-objects; both readers fail
        // closed to 0 when the key is absent or malformed, so a partially-shaped response
        // still yields an honest observation rather than a thrown check.
        JSONObject type = data.optJSONObject("type");
        JSONObject text = data.optJSONObject("text");
        double deepfakeProbability = detectorProbability(type, "deepfake");
        double artificialText = detectorProbability(text, "has_artificial");
        double naturalText = detectorProbability(text, "has_natural");
        boolean deepfakeSuspicious = deepfakeProbability > 0.5;
        boolean textSuspicious = artificialText > 0.5;

        try {
            JSONObject ai = observation(probability, suspicious);
            ai.put("is_ai_generated", suspicious);

            JSONObject deepfake = observation(deepfakeProbability, deepfakeSuspicious);
            deepfake.put("is_deepfake", deepfakeSuspicious);

            // Text present in the scene (has_natural) is not an accusation: only text added
            // after the shot (has_artificial) is flagged.
            JSONObject embeddedText = observation(artificialText, textSuspicious);
            embeddedText.put("has_artificial", artificialText);
            embeddedText.put("has_natural", naturalText);

            JSONObject verdict = new JSONObject();
            verdict.put("image_authenticity_checked", true);
            verdict.put("ai_generated", ai);
            verdict.put("deepfake", deepfake);
            verdict.put("embedded_text", embeddedText);
            return verdict;
        } catch (Exception error) {
            // Unreachable with the guarded values above; the contract is still never-throwing.
            return failure("SightEngine returned an unreadable verdict.");
        }
    }

    /**
     * One detector's reading, in the shape every IRIS surface reads.
     *
     * Every detector answers with the same fields so a client can render any of them
     * without knowing which model produced it. Fields never make one detector's output
     * a conclusion about another's.
     */
    private static JSONObject observation(double score, boolean suspicious) throws Exception {
        JSONObject payload = new JSONObject();
        payload.put("suspicion_score", score);
        payload.put("confidence", score);
        payload.put("is_suspicious", suspicious);
        payload.put("model", "SightEngine");
        payload.put("status", "ok");
        payload.put("error", JSONObject.NULL);
        return payload;
    }

    /**
     * Reads one probability key out of a SightEngine sub-object. SightEngine has shipped
     * numbers, missing keys and unparseable strings; an unknown reads as 0, the same way
     * the backend reads it — an unknown is an observation of nothing, not a verdict.
     */
    private static double detectorProbability(JSONObject container, String key) {
        if (container == null) return 0;

        Object raw = container.opt(key);
        double value;
        if (raw instanceof Number) {
            value = ((Number) raw).doubleValue();
        } else if (raw instanceof String) {
            try {
                value = Double.parseDouble((String) raw);
            } catch (NumberFormatException error) {
                return 0;
            }
        } else {
            return 0;
        }

        if (Double.isNaN(value) || Double.isInfinite(value)) return 0;
        return value;
    }

    /** The never-throwing failure shape: checked=false, so every surface shows Not assessed. */
    static JSONObject failure(String error) {
        JSONObject result = new JSONObject();
        try {
            result.put("image_authenticity_checked", false);
            JSONObject ai = new JSONObject();
            ai.put("status", "error");
            ai.put("error", error == null ? "SightEngine request failed." : error);
            result.put("ai_generated", ai);
        } catch (Exception ignored) {
        }
        return result;
    }

    /**
     * Folds the authenticity verdict into the backend's response for delivery.
     *
     * A response that already carries a completed check passes through untouched: the
     * backend ran its own check, and two verdicts for one image must never fight — the
     * backend's own answer is the one that ships. Mere presence is not a verdict: a
     * backend that could not check answers false, and letting that bin a check which
     * did finish would bill the client for an answer the user never sees.
     */
    static String mergeInto(String responseJson, JSONObject authenticity) {
        if (authenticity == null) return responseJson;
        try {
            JSONObject payload = new JSONObject(responseJson);
            if (payload.optBoolean("image_authenticity_checked", false)) return responseJson;
            payload.put("image_authenticity_checked",
                authenticity.optBoolean("image_authenticity_checked", false));
            payload.put("ai_generated", authenticity.optJSONObject("ai_generated"));
            copyDetector(payload, authenticity, "deepfake");
            copyDetector(payload, authenticity, "embedded_text");
            return payload.toString();
        } catch (Exception error) {
            return responseJson;
        }
    }

    /**
     * Carries one extra detector across a merge. Absent stays absent: a payload that
     * never ran a detector must not grow an empty verdict for it.
     */
    private static void copyDetector(JSONObject target, JSONObject source, String key)
        throws JSONException {
        JSONObject value = source == null ? null : source.optJSONObject(key);
        if (value != null) target.put(key, value);
    }

    /**
     * The claims half failed but the image half finished: deliver the verdict anyway,
     * with the backend failure riding along as the claim message (extension parity,
     * background.js:602-612 — a dead claims backend still shows the badge).
     */
    static String payloadWithClaimError(String claimError, JSONObject authenticity) {
        try {
            JSONObject payload = new JSONObject();
            payload.put("message", claimError == null || claimError.isEmpty()
                ? "IRIS could not verify the selected image." : claimError);
            payload.put("image_authenticity_checked",
                authenticity != null && authenticity.optBoolean("image_authenticity_checked", false));
            if (authenticity != null) {
                payload.put("ai_generated", authenticity.optJSONObject("ai_generated"));
                copyDetector(payload, authenticity, "deepfake");
                copyDetector(payload, authenticity, "embedded_text");
            }
            return payload.toString();
        } catch (Exception error) {
            return claimError == null ? "" : claimError;
        }
    }

    /** Decodes the payload of a data URL (data:image/png;base64,...) back to its bytes. */
    static byte[] bytesFromDataUrl(String dataUrl) {
        if (dataUrl == null) return new byte[0];
        int comma = dataUrl.indexOf(',');
        if (comma < 0) return new byte[0];
        try {
            return Base64.decode(dataUrl.substring(comma + 1), Base64.DEFAULT);
        } catch (Exception error) {
            return new byte[0];
        }
    }

    private static double probabilityOf(JSONObject data) {
        Object raw = data.opt("type");
        if (raw instanceof JSONObject) {
            JSONObject object = (JSONObject) raw;
            raw = object.opt("ai_generated");
            if (raw == null || raw == JSONObject.NULL) raw = object.opt("probability");
        }

        double probability;
        if (raw instanceof Number) {
            probability = ((Number) raw).doubleValue();
        } else if (raw instanceof String) {
            try {
                probability = Double.parseDouble((String) raw);
            } catch (NumberFormatException error) {
                probability = 0;
            }
        } else {
            probability = 0;
        }

        if (Double.isNaN(probability) || Double.isInfinite(probability)) return 0;
        return probability;
    }

    private static void writeField(OutputStream output, String boundary, String name, String value)
        throws Exception {
        output.write(("--" + boundary + "\r\n").getBytes(StandardCharsets.UTF_8));
        output.write(("Content-Disposition: form-data; name=\"" + name + "\"\r\n\r\n")
            .getBytes(StandardCharsets.UTF_8));
        output.write(value.getBytes(StandardCharsets.UTF_8));
        output.write("\r\n".getBytes(StandardCharsets.UTF_8));
    }

    private static void writeMedia(OutputStream output, String boundary, byte[] imageBytes)
        throws Exception {
        output.write(("--" + boundary + "\r\n").getBytes(StandardCharsets.UTF_8));
        output.write(("Content-Disposition: form-data; name=\"media\"; filename=\"image.jpg\"\r\n")
            .getBytes(StandardCharsets.UTF_8));
        output.write("Content-Type: image/jpeg\r\n\r\n".getBytes(StandardCharsets.UTF_8));
        output.write(imageBytes);
        output.write("\r\n".getBytes(StandardCharsets.UTF_8));
        output.write(("--" + boundary + "--\r\n").getBytes(StandardCharsets.UTF_8));
    }

    private static String readStream(InputStream inputStream) throws Exception {
        if (inputStream == null) return "";
        java.io.ByteArrayOutputStream output = new java.io.ByteArrayOutputStream();
        byte[] buffer = new byte[8192];
        int read;
        while ((read = inputStream.read(buffer)) != -1) {
            output.write(buffer, 0, read);
        }
        return output.toString(StandardCharsets.UTF_8.name());
    }
}
