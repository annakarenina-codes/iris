package com.iris.app;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import android.text.TextUtils;
import android.util.Log;

import java.util.ArrayList;
import java.util.List;

/**
 * On-device store for successful verification checks.
 *
 * History is a convenience, never a requirement: every public method swallows its own
 * failures so a storage problem cannot break the result-delivery paths that call it.
 */
final class HistoryStore extends SQLiteOpenHelper {
    private static final String TAG = "IrisHistory";
    private static final String DATABASE_NAME = "iris_history.db";
    private static final int DATABASE_VERSION = 1;
    private static final int MAX_ENTRIES = 200;
    private static final int PREVIEW_LIMIT = 160;

    HistoryStore(Context context) {
        super(context, DATABASE_NAME, null, DATABASE_VERSION);
    }

    @Override
    public void onCreate(SQLiteDatabase db) {
        db.execSQL(
            "CREATE TABLE history ("
                + "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                + "checked_at INTEGER NOT NULL, "
                + "input_type TEXT NOT NULL, "
                + "preview TEXT, "
                + "verdict TEXT, "
                + "fallback TEXT, "
                + "raw_json TEXT NOT NULL)"
        );
    }

    @Override
    public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {
        // Version 1 is the first schema, so there is nothing to migrate yet.
    }

    /**
     * Records one successful check from any entry point. The result flow that calls
     * this must keep working even if the write fails, so nothing is allowed to throw.
     */
    static void record(Context context, String responseJson, String fallbackText, String inputType) {
        HistoryStore store = new HistoryStore(context);
        try {
            store.insert(responseJson, fallbackText, inputType);
        } catch (Exception error) {
            Log.w(TAG, "Could not record history entry", error);
        } finally {
            try {
                store.close();
            } catch (Exception error) {
                Log.w(TAG, "Could not close the history database", error);
            }
        }
    }

    /**
     * Stores one row for a successful check and returns its row id, or -1 on failure.
     * Preview and verdict are derived here so every entry point records them the same
     * way, while raw_json keeps the full payload for detail rendering.
     */
    long insert(String responseJson, String fallbackText, String inputType) {
        if (TextUtils.isEmpty(responseJson)) {
            Log.w(TAG, "Refusing to record an empty response payload");
            return -1;
        }

        try {
            String safeFallback = fallbackText == null ? "" : fallbackText;
            String safeInputType = TextUtils.isEmpty(inputType) ? "text" : inputType;

            IrisResultData parsed = IrisResultData.parse(responseJson, safeFallback, safeInputType);
            String preview = "";
            String verdict = "";
            if (!parsed.claims.isEmpty()) {
                IrisResultData.ClaimItem first = parsed.claims.get(0);
                preview = first.claimText;
                verdict = first.verdict == null ? "" : first.verdict;
            }
            if (TextUtils.isEmpty(preview)) preview = safeFallback;

            ContentValues values = new ContentValues();
            values.put("checked_at", System.currentTimeMillis());
            values.put("input_type", safeInputType);
            values.put("preview", truncateForPreview(preview));
            values.put("verdict", verdict);
            values.put("fallback", safeFallback);
            values.put("raw_json", responseJson);

            long rowId = getWritableDatabase().insert("history", null, values);
            if (rowId == -1) {
                Log.w(TAG, "SQLite rejected the history insert");
            }
            return rowId;
        } catch (Exception error) {
            Log.w(TAG, "Could not insert history entry", error);
            return -1;
        }
    }

    /**
     * Opens, reads, and closes in one call, for callers like the overlay panel that have
     * no store of their own. A read failure still reads as an empty list.
     */
    static List<HistoryEntry> recent(Context context, int limit) {
        HistoryStore store = new HistoryStore(context);
        try {
            return store.latest(limit);
        } finally {
            try {
                store.close();
            } catch (Exception error) {
                Log.w(TAG, "Could not close the history database", error);
            }
        }
    }

    /**
     * Returns up to the requested number of entries, newest first. A read failure
     * reads as an empty history rather than an error the UI has to handle.
     */
    List<HistoryEntry> latest(int limit) {
        List<HistoryEntry> entries = new ArrayList<>();
        Cursor cursor = null;
        try {
            int safeLimit = Math.max(0, Math.min(limit, MAX_ENTRIES));
            cursor = getReadableDatabase().query(
                "history",
                null,
                null,
                null,
                null,
                null,
                "checked_at DESC, id DESC",
                String.valueOf(safeLimit)
            );
            while (cursor.moveToNext()) {
                HistoryEntry entry = new HistoryEntry();
                entry.id = cursor.getLong(cursor.getColumnIndexOrThrow("id"));
                entry.checkedAt = cursor.getLong(cursor.getColumnIndexOrThrow("checked_at"));
                entry.inputType = cursor.getString(cursor.getColumnIndexOrThrow("input_type"));
                entry.preview = cursor.getString(cursor.getColumnIndexOrThrow("preview"));
                entry.verdict = cursor.getString(cursor.getColumnIndexOrThrow("verdict"));
                entry.fallback = cursor.getString(cursor.getColumnIndexOrThrow("fallback"));
                entry.rawJson = cursor.getString(cursor.getColumnIndexOrThrow("raw_json"));
                entries.add(entry);
            }
        } catch (Exception error) {
            Log.w(TAG, "Could not read history entries", error);
            entries.clear();
        } finally {
            if (cursor != null) {
                try {
                    cursor.close();
                } catch (Exception error) {
                    Log.w(TAG, "Could not close the history cursor", error);
                }
            }
        }
        return entries;
    }

    /** Removes every stored entry; failures are logged and ignored. */
    void clear() {
        try {
            getWritableDatabase().delete("history", null, null);
        } catch (Exception error) {
            Log.w(TAG, "Could not clear history", error);
        }
    }

    private static String truncateForPreview(String value) {
        if (value == null) return "";
        String text = value.trim();
        return text.length() > PREVIEW_LIMIT ? text.substring(0, PREVIEW_LIMIT - 3) + "..." : text;
    }

    /** One row per check; raw_json carries the full payload so detail can re-parse it. */
    static final class HistoryEntry {
        long id;
        long checkedAt;
        String inputType = "text";
        String preview = "";
        String verdict = "";
        String fallback = "";
        String rawJson = "";
    }
}
