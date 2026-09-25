# IRIS Monorepo

IRIS, or Intelligent Real-Time Information Scanner, is organized here as one monorepo with separate projects for the backend, Chrome extension frontend, and Android app mockup.

## Recent changes

### Earlier work (24–25 September)

**Check history (both frontends)**

- Android: successful checks are saved on-device in SQLite (last 200), with a History screen to reopen past results.
- Extension: checks are saved in browser storage, shown in a History card on the Options page with a Clear history button; the panel keeps the 3 most recent checks.

**Extension**

- Access-token field on the Options page for token-protected backends.
- Retried requests and a keep-alive while a check is in flight, so slow verifications don't die mid-request.
- Backend URL is stored per extension copy, so the dev build and installed build don't share settings.

**Android**

- Android Gradle plugin upgraded to 8.9.2.
- Result parsing reworked into `IrisResultData`.

### Version control (this branch, `master`)

- Initialized the monorepo as a Git repository with the full baseline committed and pushed to GitHub.
- Commits are authored as **Miaowty**; `iris-android` and `iris-extension` are tracked as embedded repositories.

### `iris-extension` — design token refresh and history detail

- Introduced shared design tokens for radii, easing, and motion (`--iris-r-*`, `--iris-ease`, `--iris-fast`, `--iris-med`) so popup, options, and overlay surfaces follow one visual rhythm.
- Reworked the brand gradient and layered shadows for better contrast past the gradient midpoint.
- Dark theme now stays on the brand: surfaces are violet-tinted steps instead of flat gray, so light and dark read as one product.
- History detail renders the full claim text in a blockquote — rows clamp to two lines, so the detail view is the only place the complete statement is readable.
- Rebuilt `dist/` artifacts and refreshed interaction-test screenshots.

### `iris-android` — dark theme, shared rendering, and tests

- **Dark theme**: `IrisUi.applyTheme()` swaps a mutable palette at every creation boundary (Activity `onCreate`, overlay build); `values-night/styles.xml` provides night resources and the system night setting is respected by default.
- The overlay repaints the theme on show and on configuration change instead of restarting the service, so a theme flip can never strand the bubble.
- **Shared result rendering**: extracted `ResultRenderer` (claim panel, navigator, error card) out of `ResultActivity`, which now delegates instead of duplicating markup.
- **History detail**: new `HistoryDetail` plus `OpenDetailTracker`, so only one recent-check detail can be expanded at a time and the panel can reposition for it.
- **Unit tests**: JUnit 4 + Robolectric setup with `HistoryDetailTest` and `IrisResultDataTest`.
- **Security hardening**: cleartext traffic is now denied globally and allowed only for emulator/localhost (`10.0.2.2`, `127.0.0.1`, `localhost`); `usesCleartextTraffic` removed from the manifest.
- Added a violet keyboard focus ring for text fields, which previously had no visible focus state.

## Structure

```text
iris/
├── iris-backend/      Python Flask backend
├── iris-extension/    Chrome browser extension frontend
└── iris-app/          Android app frontend mockup
```

## Projects

### `iris-backend`

Key files:

- `app.py`
- `requirements.txt`
- `.env`
- `pipeline/`
- `tests/`

The backend virtual environment was not copied. Recreate it inside `iris-backend/` when needed.

### `iris-extension`

Manifest V3 Chrome extension frontend for selected-text checks, right-click image OCR checks, toolbar popup controls, and backend configuration.

### `iris-app`

Copied from the current polished Android app mockup.

This is still the React/Vite mockup version. It can be migrated later into a real React Native Android project structure.

## Frontend Scripts

From the monorepo root:

```bash
pnpm --dir iris-extension build
pnpm --dir iris-app build
```

Or use the root convenience scripts:

```bash
pnpm run extension:build
pnpm run app:build
```

## Notes

Generated dependency folders and runtime artifacts were intentionally not copied:

- `node_modules/`
- `venv/`
- `dist/`
- Python caches
- local SQLite/cache files
- preview logs
- nested `.git/` folders

This keeps the monorepo clean while preserving the source and configuration needed to continue development.

## Backend diagnostics

Approved sources, how each one is read (full text or search excerpt) and the 19 September 2026 source-policy change are documented in [iris-backend/SOURCES.md](iris-backend/SOURCES.md).

Translation uses the configured OpenAI API with a bounded deadline and original-text fallback. See [translation configuration and validation](iris-backend/TRANSLATION.md).

IRIS TRACE adds a development-only request viewer with tabs, per-claim stages, OCR overlays and calibration fixtures. From `iris-backend`, run `python run_trace.py --artifacts` and open `http://127.0.0.1:5000/debug/trace`. See [TRACE setup and calibration guide](iris-backend/iris_trace/README.md).
