# IRIS Monorepo

IRIS, or Intelligent Real-Time Information Scanner, is organized here as one monorepo with separate projects for the backend, Chrome extension mockup, and Android app mockup.

## Structure

```text
iris/
├── iris-backend/      Python Flask backend
├── iris-extension/    Chrome browser extension frontend mockup
└── iris-app/          Android app frontend mockup
```

## Projects

### `iris-backend`

Copied from `C:\Users\aquarius12\iris-backend`.

Key files:

- `app.py`
- `requirements.txt`
- `.env`
- `pipeline/`
- `tests/`

The backend virtual environment was not copied. Recreate it inside `iris-backend/` when needed.

### `iris-extension`

Copied from the current polished Chrome extension mockup.

This is still the React/Vite mockup version. It can be converted later into the real Chrome extension structure with `manifest.json`, `content.js`, `background.js`, popup files, and icons.

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
