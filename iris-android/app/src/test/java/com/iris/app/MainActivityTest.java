package com.iris.app;

import android.view.View;
import android.view.ViewGroup;
import android.widget.EditText;
import android.widget.TextView;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.Robolectric;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;

import java.util.ArrayList;
import java.util.List;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

/**
 * The bring-your-own-key settings card: it renders with its explanation, saves what was
 * typed (trimmed), and reloads saved keys on the next launch — the extension settings
 * contract, kept on the device and out of the APK.
 *
 * Also the clipboard auto-open choice: off until the reader turns it on, saved the
 * moment it is flipped, and still there on the next launch.
 */
@RunWith(RobolectricTestRunner.class)
@Config(sdk = 34)
public class MainActivityTest {

    @Test
    public void sightengineCardRendersItsFieldsAndExplanation() {
        MainActivity activity = Robolectric.buildActivity(MainActivity.class).setup().get();
        List<String> texts = textsIn(activity.getWindow().getDecorView());

        assertTrue(texts.contains(activity.getString(R.string.sightengine_eyebrow)));
        assertTrue(texts.contains(activity.getString(R.string.sightengine_title)));
        assertTrue(texts.contains(activity.getString(R.string.sightengine_desc)));
        assertNotNull("the API user field must be on screen",
            fieldWithHint(activity, activity.getString(R.string.sightengine_user_hint)));
        assertNotNull("the API secret field must be on screen",
            fieldWithHint(activity, activity.getString(R.string.sightengine_secret_hint)));
        assertNotNull("the save button must be on screen",
            buttonWithText(activity, activity.getString(R.string.sightengine_save)));
    }

    @Test
    public void savingCredentialsStoresThemTrimmedAndSaysSo() {
        MainActivity activity = Robolectric.buildActivity(MainActivity.class).setup().get();

        fieldWithHint(activity, activity.getString(R.string.sightengine_user_hint))
            .setText("  user-123  ");
        fieldWithHint(activity, activity.getString(R.string.sightengine_secret_hint))
            .setText("  secret-456  ");
        buttonWithText(activity, activity.getString(R.string.sightengine_save)).performClick();

        assertEquals("user-123", IrisPrefs.getSightengineApiUser(activity));
        assertEquals("secret-456", IrisPrefs.getSightengineApiSecret(activity));
        assertTrue("the card must confirm the save",
            textsIn(activity.getWindow().getDecorView())
                .contains(activity.getString(R.string.status_sightengine_saved)));
    }

    @Test
    public void savedCredentialsPreFillTheFieldsOnTheNextLaunch() {
        IrisPrefs.setSightengineApiUser(RuntimeEnvironment.getApplication(), "stored-user");
        IrisPrefs.setSightengineApiSecret(RuntimeEnvironment.getApplication(), "stored-secret");

        MainActivity activity = Robolectric.buildActivity(MainActivity.class).setup().get();

        assertEquals("stored-user", fieldWithHint(activity,
            activity.getString(R.string.sightengine_user_hint)).getText().toString());
        assertEquals("stored-secret", fieldWithHint(activity,
            activity.getString(R.string.sightengine_secret_hint)).getText().toString());
    }

    @Test
    public void clipboardCardRendersItsExplanationAndStartsOff() {
        MainActivity activity = Robolectric.buildActivity(MainActivity.class).setup().get();
        List<String> texts = textsIn(activity.getWindow().getDecorView());

        assertTrue(texts.contains(activity.getString(R.string.clipboard_eyebrow)));
        assertTrue(texts.contains(activity.getString(R.string.clipboard_title)));
        assertTrue(texts.contains(activity.getString(R.string.clipboard_desc)));

        IrisToggleView toggle = clipboardToggleFor(activity);
        assertFalse("auto-open must stay off until the reader turns it on", toggle.isChecked());
        assertFalse(IrisPrefs.isClipboardAutoOpen(activity));
    }

    @Test
    public void togglingClipboardAutoOpenPersistsAcrossRelaunch() {
        MainActivity activity = Robolectric.buildActivity(MainActivity.class).setup().get();
        clipboardToggleFor(activity).performClick();

        assertTrue(IrisPrefs.isClipboardAutoOpen(activity));
        assertTrue(clipboardToggleFor(activity).isChecked());

        MainActivity relaunched = Robolectric.buildActivity(MainActivity.class).setup().get();
        assertTrue("the saved choice must come back checked",
            clipboardToggleFor(relaunched).isChecked());
    }

    /** The toggle sits next to its own label; the label is what makes the switch readable. */
    private static IrisToggleView clipboardToggleFor(MainActivity activity) {
        ViewGroup row = (ViewGroup) buttonWithText(
            activity,
            activity.getString(R.string.clipboard_toggle_label)
        ).getParent();
        for (int index = 0; index < row.getChildCount(); index += 1) {
            if (row.getChildAt(index) instanceof IrisToggleView) {
                return (IrisToggleView) row.getChildAt(index);
            }
        }
        throw new AssertionError("the clipboard toggle must sit next to its label");
    }

    private static EditText fieldWithHint(MainActivity activity, String hint) {
        return findField(activity.getWindow().getDecorView(), hint);
    }

    private static EditText findField(View view, String hint) {
        if (view instanceof EditText) {
            CharSequence fieldHint = ((EditText) view).getHint();
            if (fieldHint != null && hint.contentEquals(fieldHint)) {
                return (EditText) view;
            }
        }
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int index = 0; index < group.getChildCount(); index += 1) {
                EditText found = findField(group.getChildAt(index), hint);
                if (found != null) return found;
            }
        }
        return null;
    }

    private static TextView buttonWithText(MainActivity activity, String text) {
        TextView button = findButton(activity.getWindow().getDecorView(), text);
        assertNotNull("expected a view with text \"" + text + "\"", button);
        return button;
    }

    private static TextView findButton(View view, String text) {
        if (view instanceof TextView && text.equals(((TextView) view).getText().toString())) {
            return (TextView) view;
        }
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int index = 0; index < group.getChildCount(); index += 1) {
                TextView found = findButton(group.getChildAt(index), text);
                if (found != null) return found;
            }
        }
        return null;
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
            for (int index = 0; index < group.getChildCount(); index += 1) {
                collect(group.getChildAt(index), texts);
            }
        }
    }
}
