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
- Official IRIS PNG logo used for the panel, pill, popup/options pages, and Chrome extension icons.
- Toolbar popup with Open panel, Check selected text, and Options shortcuts.
- Options page for backend URL, panel visibility, Quiet Mode, theme, font size, and debug mode.

The extension sends only user-selected text or explicitly selected image data to the configured backend.

## Interaction Feedback

- Panel, pill, header, and file input stay mounted during ordinary updates and collapse/expand. Settings changes preserve controls and focus; claim navigation preserves its buttons; opening FAQ preserves the underlying result and scroll position.
- Quiet Mode removes the panel and pill when dismissed. It still mounts a result panel for an explicit context-menu check.
- Buttons and source cards provide pressed feedback. Reduced-motion preferences disable pulses, shimmer, entrances, and moving pressed/hover effects while keeping static scanning and pressed indicators.
- Position changes update the existing surface, retaining each tab's session-scoped position.

## UI Regression Checks

With development dependencies installed and Google Chrome available, run `npm run test:ui`. Set `IRIS_TEST_BROWSER` to another Playwright browser channel if needed.

The tests use the real content script and stylesheet in Chrome with simulated extension messages and verification responses. They cover selection, preserved controls/focus, claim navigation, scrolling, drag/drop, per-tab positions, Quiet Mode, and live reduced-motion changes. They do not validate backend verdict accuracy. Screenshots are written to `build/interaction-tests/`.
