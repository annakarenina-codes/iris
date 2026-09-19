# IRIS Android Frontend

This folder contains the native Android frontend for IRIS.

It is separate from `iris-app`, which remains the earlier web mockup/prototype.

## What works in this native build

- Polished IRIS-styled Android home control center with gradient brand header, official logo, bubble toggle, backend settings, manual verification, and source/privacy guidance.
- Main IRIS Bubble toggle with `ON - Bubble is visible` and `OFF - Bubble is hidden` states.
- Floating IRIS bubble with white logo background, subtle purple border, draggable position persistence, and purple pulsing scan state.
- Bubble snaps to the nearest horizontal screen edge after a drag, saves the final position, and lets a new drag interrupt the movement. Position is clamped again on screen configuration changes.
- System animation preferences apply to the scanning bubble, scan indicators, edge snapping, and tap feedback. With animations disabled, scanning uses a static logo/indicator and edge snapping is instant.
- Native ripple feedback on buttons, the bubble, toggle, navigation, and evidence cards; static pressed/focus highlights when animations are disabled.
- Overlay window stays attached through input, scanning, result, and error transitions, preserving the active paste-input references.
- Bubble paste-text panel for apps such as Facebook that copy long-pressed text without showing Android's standard text-selection toolbar.
- Explicit `Paste from Clipboard` button; clipboard is not read automatically when the bubble opens.
- Bubble-side `Choose image for OCR` action that opens Android's image picker and routes the selected image to `/verify-image`.
- Android selected-text entry through `ACTION_PROCESS_TEXT`, shown as `Check with IRIS` in supported text-selection menus.
- Android image sharing through `ACTION_SEND` for `image/*`, routed to `/verify-image`.
- Shared overlay verification flow for pasted text, selected text, shared images, and bubble-picked images: `Idle -> Scanning -> Result -> Idle`.
- Overlay result panel anchored near the bubble with claim navigation, quoted claim box, per-claim political flag, verdict badge, evidence count, evidence source cards, skipped-segment summary note, and disclaimer.
- Full-screen fallback scanning/result screens for cases where overlay permission has not been granted.
- Persistent `IRIS is active` notification while the bubble service is running; tapping the notification disables the bubble.
- Manual text verification and manual image picker through the main IRIS screen for direct backend testing.
- Backend URL setting, defaulting to `http://10.0.2.2:5000` for the Android Emulator.
- Actual IRIS PNG logo asset reused across Android headers, scanning screens, result panels, overlay bubble, and launcher icon.

## Backend URL notes

- Text and image requests allow 30 seconds to establish a connection and 120 seconds of read inactivity while waiting for the backend response. This accommodates slower verification without changing backend processing speed.
- Android Emulator to laptop Flask backend: `http://10.0.2.2:5000`
- Physical phone to laptop Flask backend: use your laptop's local network IP, such as `http://192.168.1.10:5000`
- Deployed backend: use the deployed HTTPS URL.
- On Android 17 and newer, this app requests Nearby devices (`ACCESS_LOCAL_NETWORK`) permission before connecting to a local backend. Allow it when prompted. Both text and image checks resume after permission is granted; public HTTPS backends do not require this permission.
- If permission was denied, enable Nearby devices in Android Settings > Apps > IRIS > Permissions, then retry. A running Flask server alone does not bypass Android's local-network access restriction.

## How to open

1. Open Android Studio.
2. Choose Open.
3. Select the `iris-android` folder.
4. Let Android Studio sync Gradle.
5. Run the app on a Pixel emulator or a physical Android phone.

## Testing notes

- Enable the bubble from the IRIS home screen and grant Display over other apps permission when Android asks.
- On Android 13 or newer, allow notifications so the persistent bubble toggle notification is visible.
- For Facebook text, long-press the post text, then use the IRIS Bubble's paste panel.
- For images, test both Android share sheet to IRIS and the bubble's Choose image for OCR action.
- On Android 17, test a local-backend check with Nearby devices permission initially unset: allow the prompt and confirm the pending check resumes. Also test denial (an actionable error, not a connection timeout), then grant access in Settings and retry. Repeat for the bubble and main-screen entry points, including images.
- Test clipboard behavior on real hardware before relying on Facebook as the primary field test target because some phone brands add their own clipboard layer.
- Drag to both screen edges and interrupt a snap with another drag. Rotate the device and confirm the bubble stays reachable; restart the bubble to check its saved position.
- Toggle Android's Remove animations setting before and during a check. Scanning must remain visible without pulsing/spinning, taps must still show feedback, and the bubble must snap instantly.
- Open the paste panel, paste/type text, submit it, and navigate results. Confirm the keyboard closes for scanning/results and the bubble still responds to taps after a drag.
