package com.iris.app;

import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.Robolectric;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import org.robolectric.shadows.ShadowSettings;

import java.util.ArrayList;
import java.util.List;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;
import static org.robolectric.Shadows.shadowOf;

@RunWith(RobolectricTestRunner.class)
@Config(sdk = 34)
public class VerifyTextActivityTest {

    @Test
    public void shareSheetTextResolvesVerifyTextActivity() {
        Intent intent = new Intent(Intent.ACTION_SEND).setType("text/plain");
        ResolveInfo info = RuntimeEnvironment.getApplication().getPackageManager()
                .resolveActivity(intent, PackageManager.MATCH_DEFAULT_ONLY);

        assertNotNull("ACTION_SEND text/plain must resolve to an IRIS activity", info);
        assertEquals(VerifyTextActivity.class.getName(), info.activityInfo.name);
    }

    @Test
    public void sharedTextRoutesToOverlayService() {
        ShadowSettings.setCanDrawOverlays(true);
        Intent intent = new Intent(Intent.ACTION_SEND)
                .setType("text/plain")
                .putExtra(Intent.EXTRA_TEXT, "Shared claim to check");

        VerifyTextActivity activity = Robolectric
                .buildActivity(VerifyTextActivity.class, intent).setup().get();

        Intent started = shadowOf(activity).getNextStartedService();
        assertNotNull("Overlay service must receive the shared text", started);
        assertEquals(OverlayService.ACTION_VERIFY_TEXT, started.getAction());
        assertEquals("Shared claim to check", started.getStringExtra(OverlayService.EXTRA_TEXT));
        assertTrue(activity.isFinishing());
    }

    @Test
    public void selectionToolbarIntentRoutesUnchanged() {
        ShadowSettings.setCanDrawOverlays(true);
        Intent intent = new Intent(Intent.ACTION_PROCESS_TEXT)
                .putExtra(Intent.EXTRA_PROCESS_TEXT, "Selected claim to check");

        VerifyTextActivity activity = Robolectric
                .buildActivity(VerifyTextActivity.class, intent).setup().get();

        Intent started = shadowOf(activity).getNextStartedService();
        assertNotNull("Selection toolbar flow must keep routing to the overlay", started);
        assertEquals(OverlayService.ACTION_VERIFY_TEXT, started.getAction());
        assertEquals("Selected claim to check", started.getStringExtra(OverlayService.EXTRA_TEXT));
        assertTrue(activity.isFinishing());
    }

    @Test
    public void emptyShareShowsErrorWithoutStartingVerification() {
        ShadowSettings.setCanDrawOverlays(true);
        Intent intent = new Intent(Intent.ACTION_SEND)
                .setType("text/plain")
                .putExtra(Intent.EXTRA_TEXT, "   ");

        VerifyTextActivity activity = Robolectric
                .buildActivity(VerifyTextActivity.class, intent).setup().get();

        assertNull("Blank share must not start a verification", shadowOf(activity).getNextStartedService());
        assertFalse(activity.isFinishing());

        List<String> texts = textsIn(activity.getWindow().getDecorView());
        assertTrue("Error copy pins the shared-source wording",
                texts.contains("No shared text was provided."));
        assertTrue("Eyebrow names the source", texts.contains("Shared text"));
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
            for (int i = 0; i < group.getChildCount(); i++) {
                collect(group.getChildAt(i), texts);
            }
        }
    }
}
