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

final class IrisApiClient {
    interface Callback {
        void onSuccess(String responseJson);
        void onError(String message);
    }

    private static final int CONNECT_TIMEOUT_MS = 30000;
    // Temporary calibration setting: 0 means unlimited read wait. Restore 120000 after testing.
    private static final int READ_TIMEOUT_MS = 0;
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
            try {
                String base64 = readUriAsDataUrl(context, imageUri);
                JSONObject payload = new JSONObject();
                payload.put("image_base64", base64);
                payload.put("platform", "android");
                postJsonPayload(context, "/verify-image", payload, callback);
            } catch (Exception error) {
                MAIN.post(() -> callback.onError(error.getMessage()));
            }
        });
    }

    private static void postJson(Context context, String path, JSONObject payload, Callback callback) {
        EXECUTOR.execute(() -> postJsonPayload(context, path, payload, callback));
    }

    private static void postJsonPayload(Context context, String path, JSONObject payload, Callback callback) {
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
                String message = extractBackendMessage(response, status);
                MAIN.post(() -> callback.onError(message));
                return;
            }

            MAIN.post(() -> callback.onSuccess(response));
        } catch (SocketTimeoutException error) {
            String message = connected
                ? "IRIS connected to the backend, but the network timed out while waiting for a response. Please retry."
                : "IRIS could not connect to " + IrisPrefs.getBackendUrl(context) + ". Check that the backend is running and local network access is allowed.";
            MAIN.post(() -> callback.onError(message));
        } catch (ConnectException error) {
            MAIN.post(() -> callback.onError("No connection to " + IrisPrefs.getBackendUrl(context)
                + ". Check the backend address and make sure Flask is running."));
        } catch (Exception error) {
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
}
