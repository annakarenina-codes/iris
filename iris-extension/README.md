# IRIS Chrome Extension

This folder is a Manifest V3 Chrome extension frontend for IRIS.

## Development Flow

1. Start the Flask backend, usually at `http://127.0.0.1:5000`.
2. Build the extension bundle:

```bash
npm run build
```

3. Open Chrome Extensions, enable Developer mode, choose Load unpacked, and select `iris-extension/dist`.
4. In the IRIS extension Options page, confirm the backend URL.

## Implemented Frontend Surfaces

- Floating content-script panel injected into normal `http` and `https` pages.
- Selected-text detection and explicit Check with IRIS action.
- Right-click context menu for selected text.
- Right-click context menu for images, routed to `/verify-image`.
- Manual image upload from the floating panel, routed to `/verify-image`.
- Local and webpage image drag-and-drop onto the floating panel, routed to `/verify-image`.
- Toolbar popup with Open panel, Check selected text, and Options shortcuts.
- Options page for backend URL, panel visibility, theme, font size, and debug mode.

The extension sends only user-selected text or explicitly selected image data to the configured backend.
