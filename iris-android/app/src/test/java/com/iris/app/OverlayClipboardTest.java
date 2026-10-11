package com.iris.app;

import org.junit.Test;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

/**
 * The clipboard auto-open threshold: only text long enough to be a claim fills the
 * panel. A URL tail, an emoji, or a bare name closes it instead of sitting there
 * uncheckable — measured after trimming, so pasted padding never fakes a claim.
 */
public class OverlayClipboardTest {

    @Test
    public void missingClipIsNeverAutoFilled() {
        assertFalse(OverlayService.isAutoFillableClip(null));
    }

    @Test
    public void emptyOrBlankClipIsNeverAutoFilled() {
        assertFalse(OverlayService.isAutoFillableClip(""));
        assertFalse(OverlayService.isAutoFillableClip("   \n\t  "));
    }

    @Test
    public void fragmentsShorterThanTheThresholdStayOut() {
        assertFalse("a bare name is not a claim",
            OverlayService.isAutoFillableClip("Marcos is dead"));
        assertFalse("an emoji is not a claim",
            OverlayService.isAutoFillableClip("\uD83D\uDC40"));
    }

    @Test
    public void claimLengthIsMeasuredAfterTrimming() {
        assertTrue("exactly at the threshold counts",
            OverlayService.isAutoFillableClip("Marcos is dead."));
        assertTrue("surrounding whitespace never pushes a claim out",
            OverlayService.isAutoFillableClip("  Marcos claims he won the election  "));
        assertTrue("a pasted post passes",
            OverlayService.isAutoFillableClip(
                "AFP reported the claim is false; the official record shows no such vote."));
    }
}
