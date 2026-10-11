package com.iris.app;

import android.view.View;
import android.widget.LinearLayout;

/**
 * The one expanded row in a tappable history list — the bubble panel's recent checks
 * and the full history screen both drive it, so the behavior cannot drift between them.
 *
 * Opening a row closes whichever was open before it, so the list reads as one open
 * verdict at a time, never a stack. `onSettled` fires when a collapse has settled (or
 * immediately when animations are off): the overlay uses it to re-derive its height
 * cap, while the full-screen history passes a no-op because its layout flows freely.
 */
final class OpenDetailTracker {
    private final Runnable onSettled;

    private View row;
    private LinearLayout detail;
    private HistoryStore.HistoryEntry entry;
    private String checkedAt;

    /** For hosts whose layout needs no re-measure after a collapse. */
    OpenDetailTracker() {
        this(() -> {});
    }

    OpenDetailTracker(Runnable onSettled) {
        this.onSettled = onSettled;
    }

    /** Expands `newDetail`, closing whichever row was open before it. */
    void open(View newRow, LinearLayout newDetail, HistoryStore.HistoryEntry newEntry, String newCheckedAt) {
        close();
        row = newRow;
        detail = newDetail;
        entry = newEntry;
        checkedAt = newCheckedAt;
        HistoryDetail.setExpanded(detail, true, onSettled);
        row.setSelected(true);
        row.setContentDescription(HistoryDetail.rowDescription(entry.verdict, entry.preview, checkedAt, true));
    }

    /** Collapses the open detail; a no-op when nothing is open. */
    void close() {
        if (detail == null) return;
        HistoryDetail.setExpanded(detail, false, onSettled);
        row.setSelected(false);
        row.setContentDescription(HistoryDetail.rowDescription(entry.verdict, entry.preview, checkedAt, false));
        clear();
    }

    /** Releases the tracked views without animating — for hosts rebuilding their list. */
    void clear() {
        row = null;
        detail = null;
        entry = null;
        checkedAt = null;
    }
}
