package com.iris.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Bundle;
import android.text.TextUtils;
import android.util.Log;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.List;
import java.util.Locale;

/**
 * Local list of past verification checks. A row tap expands its stored check inline;
 * ResultActivity stays reachable from inside that detail, so a glance never costs the
 * reader their place in the list.
 */
public class HistoryActivity extends Activity {
    private static final int HISTORY_LIMIT = 200;

    private final SimpleDateFormat dateFormat = new SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.getDefault());

    private HistoryStore historyStore;

    // One open detail at a time, same coordinator the bubble panel's recent checks use.
    private final OpenDetailTracker openDetail = new OpenDetailTracker();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        IrisUi.applyTheme(this);
        setTitle("IRIS History");
        historyStore = new HistoryStore(this);
    }

    @Override
    protected void onResume() {
        super.onResume();
        // Rebuilt here instead of onCreate so a check finished through the bubble while
        // this screen was paused still appears when the user comes back.
        render();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (historyStore != null) {
            try {
                historyStore.close();
            } catch (Exception error) {
                Log.w("IrisHistory", "Could not close the history database", error);
            }
        }
    }

    private void render() {
        // The old rows die with the view tree; drop the coordinator's references before
        // rebuilding so it never animates detached views on the next tap.
        openDetail.clear();
        ScrollView scrollView = new ScrollView(this);
        scrollView.setFillViewport(false);

        LinearLayout root = IrisUi.vertical(this, 18);
        root.setBackgroundColor(IrisUi.BG);
        scrollView.addView(root);

        LinearLayout panel = IrisUi.card(this, 0);
        panel.addView(panelHeader(), IrisUi.matchWrap());

        LinearLayout body = IrisUi.vertical(this, 18);
        List<HistoryStore.HistoryEntry> entries = historyStore.latest(HISTORY_LIMIT);

        if (entries.isEmpty()) {
            TextView empty = IrisUi.muted(this, "No checks yet.", 13);
            empty.setGravity(Gravity.CENTER);
            empty.setPadding(IrisUi.dp(this, 10), IrisUi.dp(this, 24), IrisUi.dp(this, 10), IrisUi.dp(this, 24));
            body.addView(empty, IrisUi.matchWrap());
        } else {
            for (HistoryStore.HistoryEntry entry : entries) {
                body.addView(historyRow(entry), IrisUi.spaced(this, 12));
            }

            Button clear = IrisUi.secondaryButton(this, "Clear history");
            clear.setOnClickListener(view -> confirmClear());
            body.addView(clear, IrisUi.spaced(this, 8));
        }

        TextView note = IrisUi.muted(this, "History is stored only on this device.", 11);
        note.setGravity(Gravity.CENTER);
        body.addView(note, IrisUi.spaced(this, 10));

        panel.addView(body, IrisUi.matchWrap());
        root.addView(panel, IrisUi.matchWrap());
        setContentView(scrollView);
    }

    private View panelHeader() {
        LinearLayout header = IrisUi.horizontal(this, 14);
        header.setBackground(IrisUi.gradient(this, 18));

        FrameLayout markHolder = new FrameLayout(this);
        markHolder.setBackground(IrisUi.rounded(this, Color.WHITE, 999));
        IrisMarkView mark = new IrisMarkView(this);
        FrameLayout.LayoutParams markParams = new FrameLayout.LayoutParams(
            IrisUi.dp(this, 24),
            IrisUi.dp(this, 24),
            Gravity.CENTER
        );
        markHolder.addView(mark, markParams);
        header.addView(markHolder, IrisUi.fixed(this, 36, 36));

        LinearLayout copy = IrisUi.vertical(this, 0);
        TextView name = IrisUi.text(this, "IRIS", 20, Color.WHITE, Typeface.BOLD);
        name.setIncludeFontPadding(false);
        TextView label = IrisUi.text(this, "CHECK HISTORY", 10, Color.WHITE, Typeface.BOLD);
        label.setAlpha(0.82f);
        label.setLetterSpacing(0.1f);
        copy.addView(name, IrisUi.matchWrap());
        copy.addView(label, IrisUi.matchWrap());

        LinearLayout.LayoutParams copyParams = IrisUi.rowWeight(1);
        copyParams.setMargins(IrisUi.dp(this, 10), 0, 0, 0);
        header.addView(copy, copyParams);

        Button close = new Button(this);
        close.setText("X");
        close.setTextColor(Color.WHITE);
        close.setTextSize(13);
        close.setAllCaps(false);
        close.setBackground(IrisUi.rounded(this, Color.argb(45, 255, 255, 255), 999));
        IrisUi.touchFeedback(close, 999);
        close.setOnClickListener(view -> finish());
        header.addView(close, IrisUi.fixed(this, 40, 40));
        return header;
    }

    private View historyRow(HistoryStore.HistoryEntry entry) {
        // The row keeps its own card; the detail rides in the same cell beneath it so
        // list spacing stays what it was whether the row is open or shut.
        LinearLayout cell = IrisUi.vertical(this, 0);
        LinearLayout detail = IrisUi.vertical(this, 0);
        detail.setVisibility(View.GONE);
        String checkedAt = dateFormat.format(new Date(entry.checkedAt));

        LinearLayout row = IrisUi.horizontal(this, 13);
        row.setClickable(true);
        IrisUi.touchFeedback(row, 14);
        row.setBackground(IrisUi.bordered(
            this,
            IrisUi.verdictBackground(entry.verdict),
            14,
            IrisUi.verdictBorder(entry.verdict)
        ));

        int color = IrisUi.verdictColor(entry.verdict);
        TextView icon = new TextView(this);
        icon.setText(IrisUi.verdictIcon(entry.verdict));
        icon.setTextSize(17);
        icon.setTextColor(color);
        icon.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        icon.setGravity(Gravity.CENTER);
        row.addView(icon, IrisUi.fixed(this, 40, 40));

        LinearLayout copy = IrisUi.vertical(this, 0);

        String verdictLabel = TextUtils.isEmpty(entry.verdict) ? "Result" : entry.verdict;
        copy.addView(IrisUi.text(this, verdictLabel, 15.5f, color, Typeface.BOLD), IrisUi.matchWrap());

        TextView preview = IrisUi.text(this, entry.preview, 13, IrisUi.TEXT, Typeface.NORMAL);
        preview.setMaxLines(2);
        preview.setEllipsize(TextUtils.TruncateAt.END);
        copy.addView(preview, IrisUi.spaced(this, 4));

        LinearLayout meta = IrisUi.horizontal(this, 0);
        meta.addView(IrisUi.eyebrow(this, "image".equals(entry.inputType) ? "Image" : "Text"), IrisUi.rowWeight(1));
        TextView date = IrisUi.muted(this, checkedAt, 11);
        date.setGravity(Gravity.END);
        meta.addView(date, IrisUi.rowWeight(1));
        copy.addView(meta, IrisUi.spaced(this, 6));

        LinearLayout.LayoutParams copyParams = IrisUi.rowWeight(1);
        copyParams.leftMargin = IrisUi.dp(this, 12);
        row.addView(copy, copyParams);

        row.setContentDescription(HistoryDetail.rowDescription(entry.verdict, entry.preview, checkedAt, false));
        row.setOnClickListener(view -> toggleDetail(entry, row, detail, checkedAt));

        cell.addView(row, IrisUi.matchWrap());
        cell.addView(detail, IrisUi.spaced(this, 8));
        return cell;
    }

    /**
     * Row taps expand the stored check in place; ResultActivity now only opens from
     * the detail's own button, so a quick glance costs no navigation. One row at a
     * time: opening another closes the last, matching the overlay panel.
     */
    private void toggleDetail(HistoryStore.HistoryEntry entry, View row, LinearLayout detail, String checkedAt) {
        if (row.isSelected()) {
            openDetail.close();
            return;
        }
        // Parse on first tap only: an unopened payload costs the list nothing.
        if (detail.getChildCount() == 0) {
            detail.addView(
                HistoryDetail.build(this, entry, checkedAt, () -> openFullResult(entry)),
                IrisUi.matchWrap()
            );
        }
        openDetail.open(row, detail, entry, checkedAt);
    }

    private void openFullResult(HistoryStore.HistoryEntry entry) {
        Intent intent = new Intent(this, ResultActivity.class);
        intent.putExtra(ResultActivity.EXTRA_RESPONSE_JSON, entry.rawJson);
        intent.putExtra(ResultActivity.EXTRA_FALLBACK_TEXT, entry.fallback);
        intent.putExtra(ResultActivity.EXTRA_INPUT_TYPE, entry.inputType);
        startActivity(intent);
    }

    private void confirmClear() {
        new AlertDialog.Builder(this)
            .setTitle("Clear history")
            .setMessage("Delete all saved checks from this device? This cannot be undone.")
            .setPositiveButton("Clear", (dialog, which) -> {
                historyStore.clear();
                render();
            })
            .setNegativeButton("Cancel", null)
            .show();
    }
}
