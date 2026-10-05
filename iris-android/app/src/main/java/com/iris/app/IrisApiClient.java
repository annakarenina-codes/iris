package com.iris.app;

import android.content.Context;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import android.util.Base64;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.SocketTimeoutException;
import java.net.ConnectException;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

final class IrisApiClient {
    interface Callback {
        void onSuccess(String responseJson);
        void onError(String message);
    }

    private static final int CONNECT_TIMEOUT_MS = 30000;
    // The slowest post measured took 195 seconds, so the deadline sits above that and below
    // the five minutes a hosting edge proxy usually allows. With no deadline at all, a phone
    // that lost mobile data mid-check waited on a result that was never coming.
    private static final int READ_TIMEOUT_MS = 180000;
    // A connection that never opened, or dropped part-way, earns one retry. Per-claim verdicts
    // are cached on the backend, so a second attempt usually answers in seconds.
    private static final int RETRY_DELAY_MS = 1500;
    // Read from local.properties at build time, which git ignores. This repository is
    // public, and a token committed to it is a token anyone can spend.
    private static final String ACCESS_TOKEN = BuildConfig.IRIS_ACCESS_TOKEN;
    private static final ExecutorService EXECUTOR = Executors.newCachedThreadPool();
    private static final Handler MAIN = new Handler(Looper.getMainLooper());

    private IrisApiClient() {}

    static void verifyText(Context context, String text, Callback callback) {
        try {
            JSONObject payload = new JSONObject();
            payload.put("text", text == null ? "" : text.trim());
            payload.put("platform", "android");
            postJson(context, "/verify", payload, callback);
        } catch (Exception error) {
            callback.onError(error.getMessage());
        }
    }

    static void verifyImageUri(Context context, Uri imageUri, Callback callback) {
        EXECUTOR.execute(() -> {
            String base64;
            try {
                base64 = readUriAsDataUrl(context, imageUri);
            } catch (Exception error) {
                MAIN.post(() -> callback.onError(error.getMessage()));
                return;
            }

            try {
                JSONObject payload = new JSONObject();
                payload.put("image_base64", base64);
                payload.put("platform", "android");

                // Two independent halves, started side by side (extension parity,
                // background.js:563 Promise.allSettled): the claims post and the
                // SightEngine check can each carry the result alone, so neither
                // failure is allowed to discard the other's verdict. If the backend
                // ever ships its own verdict for platform==android, drop this call to
                // save the quota — mergeInto already ensures only one verdict ships.
                Future<JSONObject> authenticity = EXECUTOR.submit(() ->
                    SightEngineAuthenticity.check(context,
                        SightEngineAuthenticity.bytesFromDataUrl(base64)));

                // Already on a worker thread, reading the image, so this goes straight to
                // the request rather than queueing a second hop. Attempt zero: the image
                // path gets the same one retry as the text path.
                postJsonPayload(context, "/verify-image", payload,
                    joinedCallback(callback, authenticity), 0);
            } catch (Exception error) {
                MAIN.post(() -> callback.onError(error.getMessage()));
            }
        });
    }

    /**
     * Delivers one image check after both halves have settled.
     *
     * Invoked on the main thread. When the SightEngine half is already finished — the
     * common case, since it answers in seconds while the claims post can take a minute —
     * joining is instant and stays put. A half still in flight must never block the UI:
     * it gets a worker, and the final delivery hops back to the main thread. Either half
     * alone is a result — a dead claims backend still shows the image badge (the backend
     * failure rides along as the claim message), and a SightEngine miss only marks the
     * badge "not assessed". Only when BOTH halves fail does the caller see a plain error
     * (extension parity, background.js:602-612).
     */
    static Callback joinedCallback(Callback callback, Future<JSONObject> authenticity) {
        return new Callback() {
            @Override
            public void onSuccess(String responseJson) {
                if (authenticity.isDone()) {
                    callback.onSuccess(SightEngineAuthenticity.mergeInto(responseJson, await(authenticity)));
                    return;
                }
                EXECUTOR.execute(() -> {
                    String merged = SightEngineAuthenticity.mergeInto(responseJson, await(authenticity));
                    MAIN.post(() -> callback.onSuccess(merged));
                });
            }

            @Override
            public void onError(String message) {
                if (authenticity.isDone()) {
                    deliverErrorOrVerdict(callback, message, await(authenticity));
                    return;
                }
                EXECUTOR.execute(() -> {
                    JSONObject verdict = await(authenticity);
                    MAIN.post(() -> deliverErrorOrVerdict(callback, message, verdict));
                });
            }
        };
    }

    /** A surviving image verdict outranks a dead claims half; only both-dead is an error. */
    private static void deliverErrorOrVerdict(Callback callback, String message, JSONObject verdict) {
        if (verdict != null && verdict.optBoolean("image_authenticity_checked", false)) {
            callback.onSuccess(SightEngineAuthenticity.payloadWithClaimError(message, verdict));
        } else {
            callback.onError(message);
        }
    }

    /** Bounded by the check's own connect+read deadlines; this is the backstop. */
    private static JSONObject await(Future<JSONObject> authenticity) {
        try {
            JSONObject verdict = authenticity.get(50, TimeUnit.SECONDS);
            return verdict != null
                ? verdict
                : SightEngineAuthenticity.failure("SightEngine check failed.");
        } catch (Exception error) {
            authenticity.cancel(true);
            return SightEngineAuthenticity.failure("SightEngine request failed.");
        }
    }

    private static void postJson(Context context, String path, JSONObject payload, Callback callback) {
        EXECUTOR.execute(() -> postJsonPayload(context, path, payload, callback, 0));
    }

    /**
     * Tries the request once more after a short pause, and says whether it did.
     *
     * Only the first failure is retried: a read that has already spent its 180 seconds is not
     * worth spending another 180 on, and the caller decides which failures qualify.
     */
    private static boolean retryOnce(Context context, String path, JSONObject payload,
                                     Callback callback, int attempt) {
        if (attempt > 0) return false;

        EXECUTOR.execute(() -> {
            try {
                Thread.sleep(RETRY_DELAY_MS);
            } catch (InterruptedException interrupted) {
                Thread.currentThread().interrupt();
            }
            postJsonPayload(context, path, payload, callback, attempt + 1);
        });
        return true;
    }

    private static void postJsonPayload(Context context, String path, JSONObject payload,
                                        Callback callback, int attempt) {
        HttpURLConnection connection = null;
        boolean connected = false;

        try {
            URL url = new URL(IrisPrefs.getBackendUrl(context) + path);
            if (BackendAccessActivity.needsPermission(context, url)) {
                MAIN.post(() -> BackendAccessActivity.requestAccess(context,
                    () -> postJson(context, path, payload, callback), callback::onError));
                return;
            }
            connection = (HttpURLConnection) url.openConnection();
            connection.setRequestMethod("POST");
            connection.setConnectTimeout(CONNECT_TIMEOUT_MS);
            connection.setReadTimeout(READ_TIMEOUT_MS);
            connection.setRequestProperty("Content-Type", "application/json");
            if (!ACCESS_TOKEN.isEmpty()) {
                connection.setRequestProperty("X-IRIS-Token", ACCESS_TOKEN);
            }
            connection.setDoOutput(true);
            connection.connect();
            connected = true;

            byte[] body = payload.toString().getBytes(StandardCharsets.UTF_8);
            try (OutputStream outputStream = connection.getOutputStream()) {
                outputStream.write(body);
            }

            int status = connection.getResponseCode();
            InputStream inputStream = status >= 200 && status < 300
                ? connection.getInputStream()
                : connection.getErrorStream();
            String response = readStream(inputStream);

            if (status < 200 || status >= 300) {
                if (carriesAuthenticityVerdict(response)) {
                    // An OCR-stop response still carries a completed image verdict: the
                    // image half runs independently of the text half, so a real badge
                    // must reach the screen instead of collapsing into a bare error.
                    MAIN.post(() -> callback.onSuccess(response));
                    return;
                }
                String message = extractBackendMessage(response, status);
                MAIN.post(() -> callback.onError(message));
                return;
            }

            MAIN.post(() -> callback.onSuccess(response));
        } catch (SocketTimeoutException error) {
            // A read that timed out has already waited the full deadline; only a connection
            // that never opened is worth trying again.
            if (!connected && retryOnce(context, path, payload, callback, attempt)) return;

            String message = connected
                ? "IRIS connected to the backend, but the network timed out while waiting for a response. Please retry."
                : "IRIS could not connect to " + IrisPrefs.getBackendUrl(context) + ". Check that the backend is running and local network access is allowed.";
            MAIN.post(() -> callback.onError(message));
        } catch (ConnectException error) {
            if (retryOnce(context, path, payload, callback, attempt)) return;

            MAIN.post(() -> callback.onError("No connection to " + IrisPrefs.getBackendUrl(context)
                + ". Check the backend address and make sure Flask is running."));
        } catch (Exception error) {
            // The mobile-data case: the connection opened and then went away mid-response.
            if (connected && retryOnce(context, path, payload, callback, attempt)) return;

            MAIN.post(() -> callback.onError(error.getMessage() == null ? "IRIS request failed." : error.getMessage()));
        } finally {
            if (connection != null) connection.disconnect();
        }
    }

    private static String readUriAsDataUrl(Context context, Uri uri) throws Exception {
        if (uri == null) throw new IllegalArgumentException("No image was provided.");

        String mimeType = context.getContentResolver().getType(uri);
        if (mimeType == null || !mimeType.startsWith("image/") || "image/gif".equalsIgnoreCase(mimeType)) {
            throw new IllegalArgumentException("Choose a PNG, JPEG, WEBP, BMP, or TIFF image.");
        }

        byte[] bytes;
        try (InputStream inputStream = context.getContentResolver().openInputStream(uri)) {
            if (inputStream == null) throw new IllegalArgumentException("IRIS could not open the selected image.");
            bytes = readBytes(inputStream);
        }

        return "data:" + mimeType + ";base64," + Base64.encodeToString(bytes, Base64.NO_WRAP);
    }

    private static byte[] readBytes(InputStream inputStream) throws Exception {
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        byte[] buffer = new byte[8192];
        int read;
        while ((read = inputStream.read(buffer)) != -1) {
            output.write(buffer, 0, read);
        }
        return output.toByteArray();
    }

    private static String readStream(InputStream inputStream) throws Exception {
        if (inputStream == null) return "";
        return new String(readBytes(inputStream), StandardCharsets.UTF_8);
    }

    private static String extractBackendMessage(String response, int status) {
        try {
            JSONObject payload = new JSONObject(response);
            String message = payload.optString("message", payload.optString("error", ""));
            if (!message.isEmpty()) return message;
        } catch (Exception ignored) {
        }
        return "IRIS backend request failed with HTTP " + status + ".";
    }

    /**
     * True when a non-2xx body still carries a completed image verdict worth rendering.
     *
     * image_authenticity_checked is only true when the check actually ran and finished;
     * every failure shape (missing creds, timeout, undecodable image) reports false and
     * stays the error it already was.
     */
    static boolean carriesAuthenticityVerdict(String response) {
        try {
            return new JSONObject(response).optBoolean("image_authenticity_checked", false);
        } catch (Exception ignored) {
            return false;
        }
    }
}
