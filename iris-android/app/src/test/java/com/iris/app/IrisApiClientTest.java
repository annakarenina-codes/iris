package com.iris.app;

import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.Config;

import java.util.concurrent.Future;
import java.util.concurrent.FutureTask;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

@RunWith(RobolectricTestRunner.class)
@Config(sdk = 34)
public class IrisApiClientTest {

    @Test
    public void completedImageVerdictsAreDeliveredAsResultsEvenOnAnErrorStatus() {
        // The OCR-stop responses carry a completed image verdict: the image half ran
        // independently of the text half, and a real badge must reach the screen.
        assertTrue(IrisApiClient.carriesAuthenticityVerdict(
            "{\"image_authenticity_checked\": true, \"ai_generated\": {\"status\": \"ok\"}}"));
    }

    @Test
    public void failedOrMissingChecksKeepTheErrorTheyCameWith() {
        assertFalse(IrisApiClient.carriesAuthenticityVerdict(
            "{\"image_authenticity_checked\": false, \"ai_generated\": {\"status\": \"error\"}}"));
        assertFalse(IrisApiClient.carriesAuthenticityVerdict(
            "{\"message\": \"IRIS could not process the submitted image.\"}"));
        assertFalse(IrisApiClient.carriesAuthenticityVerdict("not json"));
        assertFalse(IrisApiClient.carriesAuthenticityVerdict(""));
    }

    // --- joinedCallback: either half alone is a result; only both-dead is an error.
    // All tests use an already-completed future, so the join takes the synchronous
    // fast path and no background hop can race the assertions. ---

    @Test
    public void aClaimsSuccessCarriesTheJoinedImageVerdict() throws Exception {
        RecordingCallback recorder = new RecordingCallback();

        IrisApiClient.joinedCallback(recorder, completed(
                SightEngineAuthenticity.parseVerdict(200, "{\"type\": 0.9}")))
            .onSuccess("{\"claims\": [], \"message\": \"ok\"}");

        assertNull(recorder.error);
        JSONObject merged = new JSONObject(recorder.success);
        assertTrue(merged.getBoolean("image_authenticity_checked"));
        assertEquals(0.9, merged.getJSONObject("ai_generated").getDouble("suspicion_score"), 0.0001);
        assertTrue(merged.has("claims"));
    }

    @Test
    public void aBackendThatAlreadyRanTheCheckKeepsItsOwnVerdict() {
        RecordingCallback recorder = new RecordingCallback();
        String backend = "{\"image_authenticity_checked\": true, "
            + "\"ai_generated\": {\"model\": \"backend-ran-this\"}, \"claims\": []}";

        IrisApiClient.joinedCallback(recorder, completed(
                SightEngineAuthenticity.parseVerdict(200, "{\"type\": 0.9}")))
            .onSuccess(backend);

        assertEquals("the backend's own verdict ships, never two that fight",
            backend, recorder.success);
    }

    @Test
    public void aDeadClaimsBackendStillDeliversACompletedImageVerdict() throws Exception {
        RecordingCallback recorder = new RecordingCallback();

        IrisApiClient.joinedCallback(recorder, completed(
                SightEngineAuthenticity.parseVerdict(200, "{\"type\": 0.9}")))
            .onError("IRIS could not reach the server.");

        assertNull(recorder.error);
        JSONObject payload = new JSONObject(recorder.success);
        assertEquals("the claims failure rides along as the message",
            "IRIS could not reach the server.", payload.getString("message"));
        assertTrue(payload.getBoolean("image_authenticity_checked"));
    }

    @Test
    public void anUnassessedImageKeepsTheClaimsErrorAsAPlainError() {
        RecordingCallback recorder = new RecordingCallback();

        IrisApiClient.joinedCallback(recorder, completed(
                SightEngineAuthenticity.failure("SightEngine credentials not configured.")))
            .onError("IRIS could not reach the server.");

        assertNull("both halves are dead: there is no result to show", recorder.success);
        assertEquals("IRIS could not reach the server.", recorder.error);
    }

    @Test
    public void aNullVerdictFromTheFutureCountsAsAFailedHalf() {
        RecordingCallback recorder = new RecordingCallback();

        IrisApiClient.joinedCallback(recorder, completed(null))
            .onError("IRIS could not reach the server.");

        assertNull(recorder.success);
        assertEquals("IRIS could not reach the server.", recorder.error);
    }

    @Test
    public void aClaimsSuccessWithAFailedImageHalfStillDeliversTheClaims() throws Exception {
        RecordingCallback recorder = new RecordingCallback();

        IrisApiClient.joinedCallback(recorder, completed(
                SightEngineAuthenticity.failure("SightEngine credentials not configured.")))
            .onSuccess("{\"claims\": [{\"claim_text\": \"A claim\", \"verdict\": \"Verified\"}]}");

        assertNull(recorder.error);
        JSONObject merged = new JSONObject(recorder.success);
        assertFalse("the honest not-assessed state ships", merged.getBoolean("image_authenticity_checked"));
        assertTrue(merged.has("claims"));
    }

    private static Future<JSONObject> completed(JSONObject value) {
        FutureTask<JSONObject> task = new FutureTask<>(() -> value);
        task.run();
        return task;
    }

    private static final class RecordingCallback implements IrisApiClient.Callback {
        String success;
        String error;

        @Override
        public void onSuccess(String responseJson) {
            success = responseJson;
        }

        @Override
        public void onError(String message) {
            error = message;
        }
    }
}
