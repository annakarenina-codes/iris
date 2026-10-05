package com.iris.app;

import android.content.Context;
import android.view.View;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;

import java.util.Locale;

import static org.junit.Assert.assertEquals;

@RunWith(RobolectricTestRunner.class)
@Config(sdk = 34)
public class IrisLocaleTest {

    @Test
    public void savedChoiceResolvesResources() {
        Context app = RuntimeEnvironment.getApplication();
        IrisPrefs.setUiLanguage(app, "tl");
        Context wrapped = IrisLocale.wrap(app);

        assertEquals("Wika ng app", wrapped.getResources().getString(R.string.language_title));
        assertEquals("Suriin gamit ang IRIS",
                wrapped.getResources().getString(R.string.process_text_label));
    }

    @Test
    public void withoutSavedChoiceResourcesStayEnglish() {
        Context app = RuntimeEnvironment.getApplication();
        Context wrapped = IrisLocale.wrap(app);

        assertEquals("App language", wrapped.getResources().getString(R.string.language_title));
    }

    @Test
    public void filipinoSystemLocaleResolvesToTagalogResources() {
        assertEquals("tl", IrisLocale.resolveSystem(new Locale("fil")));
    }

    @Test
    public void supportedSystemLocaleKeepsItsCode() {
        assertEquals("fr", IrisLocale.resolveSystem(new Locale("fr")));
        assertEquals("ar", IrisLocale.resolveSystem(new Locale("ar")));
    }

    @Test
    public void unsupportedSystemLocaleFallsBackToEnglish() {
        assertEquals("en", IrisLocale.resolveSystem(new Locale("de")));
    }

    @Test
    public void nativeLabelsMatchTheExtensionList() {
        assertEquals("English", IrisLocale.label("en"));
        assertEquals("Tagalog", IrisLocale.label("tl"));
        assertEquals("\u4e2d\u6587", IrisLocale.label("zh"));
    }

    @Test
    public void arabicWrapsRightToLeft() {
        Context app = RuntimeEnvironment.getApplication();
        IrisPrefs.setUiLanguage(app, "ar");
        Context wrapped = IrisLocale.wrap(app);

        assertEquals(View.LAYOUT_DIRECTION_RTL,
                wrapped.getResources().getConfiguration().getLayoutDirection());
    }

    @Test
    public void processTextLabelMatchesExtensionInEveryLanguage() {
        // Byte-for-byte parity with the extension's i18n.js btn.check, all eight languages.
        String[] expected = {
            "Check with IRIS",
            "Suriin gamit ang IRIS",
            "\u7528 IRIS \u68c0\u67e5",
            "IRIS\u3067\u30c1\u30a7\u30c3\u30af",
            "V\u00e9rifier avec IRIS",
            "Verificar con IRIS",
            "\u062a\u062d\u0642\u0642 \u0628\u0627\u0633\u062a\u062e\u062f\u0627\u0645 IRIS",
            "IRIS \u0938\u0947 \u091c\u093e\u0901\u091a\u0947\u0902",
        };
        Context app = RuntimeEnvironment.getApplication();
        for (int i = 0; i < IrisLocale.LANGUAGES.length; i++) {
            IrisPrefs.setUiLanguage(app, IrisLocale.LANGUAGES[i][0]);
            Context wrapped = IrisLocale.wrap(app);
            assertEquals("language " + IrisLocale.LANGUAGES[i][0],
                    expected[i], wrapped.getResources().getString(R.string.process_text_label));
        }
    }
}
