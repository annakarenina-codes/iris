# IRIS Monorepo

IRIS, or Intelligent Real-Time Information Scanner, is organized here as one monorepo with separate projects for the backend, Chrome extension frontend, and Android app mockup.

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
