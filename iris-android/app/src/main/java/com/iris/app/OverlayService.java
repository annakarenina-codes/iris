package com.iris.app;

import android.animation.Animator;
import android.animation.AnimatorListenerAdapter;
import android.animation.ValueAnimator;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.res.Configuration;
import android.graphics.Color;
import android.graphics.Insets;
import android.graphics.PixelFormat;
import android.graphics.Rect;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Build;
import android.os.IBinder;
import android.provider.Settings;
import android.text.InputType;
import android.text.TextUtils;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewConfiguration;
import android.view.WindowInsets;
import android.view.WindowManager;
import android.view.WindowMetrics;
import android.view.animation.DecelerateInterpolator;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

public class OverlayService extends Service {
    public static final String ACTION_SHOW = "com.iris.app.action.SHOW_BUBBLE";
    public static final String ACTION_STOP = "com.iris.app.action.STOP_BUBBLE";
    public static final String ACTION_VERIFY_TEXT = "com.iris.app.action.VERIFY_TEXT";
    public static final String ACTION_VERIFY_IMAGE_URI = "com.iris.app.action.VERIFY_IMAGE_URI";
    public static final String EXTRA_TEXT = "extra_text";
    public static final String EXTRA_IMAGE_URI = "extra_image_uri";

    private static final String NOTIFICATION_CHANNEL_ID = "iris_bubble";
    private static final int NOTIFICATION_ID = 8201;
    private static final int STATE_IDLE = 0;
    private static final int STATE_INPUT = 1;
    private static final int STATE_SCANNING = 2;
    private static final int STATE_RESULT = 3;
    private static final int STATE_ERROR = 4;

    private WindowManager windowManager;
    private IrisBubbleView bubble;
    private LinearLayout panel;
    private EditText claimInput;
    private TextView panelStatus;
    private WindowManager.LayoutParams bubbleParams;
    private WindowManager.LayoutParams panelParams;
    private int startX;
    private int startY;
    private float touchX;
    private float touchY;
    private boolean moved;
    private ValueAnimator snapAnimator;
    private int state = STATE_IDLE;
    private long requestToken;
    private IrisResultData resultData;
    private int claimIndex;
    private String currentFallbackText = "";
    private String currentInputType = "text";

    @Override
    public void onCreate() {
        super.onCreate();
        windowManager = (WindowManager) getSystemService(WINDOW_SERVICE);
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        String action = intent == null ? ACTION_SHOW : intent.getAction();

        if (ACTION_STOP.equals(action)) {
            stopAndDisable();
            return START_NOT_STICKY;
        }

        if (!Settings.canDrawOverlays(this)) {
            IrisPrefs.setBubbleEnabled(this, false);
            stopSelf();
            return START_NOT_STICKY;
        }

        IrisPrefs.setBubbleEnabled(this, true);
        showActiveNotification();
        ensureBubble();

        if (ACTION_VERIFY_TEXT.equals(action)) {
            String text = intent == null ? "" : intent.getStringExtra(EXTRA_TEXT);
            verifyTextSource(text);
        } else if (ACTION_VERIFY_IMAGE_URI.equals(action)) {
            String value = intent == null ? "" : intent.getStringExtra(EXTRA_IMAGE_URI);
            verifyImageSource(TextUtils.isEmpty(value) ? null : Uri.parse(value));
        }

        return START_STICKY;
    }

    private void ensureBubble() {
        if (bubble != null && bubble.getParent() != null) return;

        bubble = new IrisBubbleView(this);
        bubble.setPadding(IrisUi.dp(this, 14), IrisUi.dp(this, 14), IrisUi.dp(this, 14), IrisUi.dp(this, 14));
        bubble.setElevation(IrisUi.dp(this, 12));

        IrisMarkView mark = new IrisMarkView(this);
        FrameLayout.LayoutParams markParams = new FrameLayout.LayoutParams(
            IrisUi.dp(this, 34),
            IrisUi.dp(this, 34),
            Gravity.CENTER
        );
        bubble.addView(mark, markParams);

        int size = IrisUi.dp(this, 68);
        bubbleParams = new WindowManager.LayoutParams(
            size,
            size,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
            PixelFormat.TRANSLUCENT
        );
        bubbleParams.gravity = Gravity.TOP | Gravity.LEFT;
        setSavedOrDefaultBubblePosition(size);

        bubble.setOnTouchListener((view, event) -> handleBubbleTouch(event));
        bubble.setOnClickListener(view -> handleBubbleTap());
        IrisMotion.observe(bubble, () -> {
            if (snapAnimator != null && !IrisMotion.animationsEnabled()) snapToEdge(false);
        });
        windowManager.addView(bubble, bubbleParams);
    }

    private void setSavedOrDefaultBubblePosition(int size) {
        int screenWidth = getResources().getDisplayMetrics().widthPixels;
        int screenHeight = getResources().getDisplayMetrics().heightPixels;
        int fallbackX = Math.max(IrisUi.dp(this, 14), screenWidth - size - IrisUi.dp(this, 14));
        int fallbackY = Math.max(IrisUi.dp(this, 80), screenHeight - size - IrisUi.dp(this, 120));
        bubbleParams.x = IrisPrefs.getBubbleX(this, fallbackX);
        bubbleParams.y = IrisPrefs.getBubbleY(this, fallbackY);
        clampBubblePosition();
    }

    private boolean handleBubbleTouch(MotionEvent event) {
        if (bubbleParams == null) return false;

        switch (event.getAction()) {
            case MotionEvent.ACTION_DOWN:
                cancelSnap();
                startX = bubbleParams.x;
                startY = bubbleParams.y;
                touchX = event.getRawX();
                touchY = event.getRawY();
                moved = false;
                bubble.drawableHotspotChanged(event.getX(), event.getY());
                bubble.setPressed(true);
                return true;
            case MotionEvent.ACTION_MOVE:
                if (distanceFromStart(event) > ViewConfiguration.get(this).getScaledTouchSlop()) moved = true;
                if (!moved) return true;
                bubble.setPressed(false);
                bubbleParams.x = startX + (int) (event.getRawX() - touchX);
                bubbleParams.y = startY + (int) (event.getRawY() - touchY);
                clampBubblePosition();
                windowManager.updateViewLayout(bubble, bubbleParams);
                if (panel != null) positionPanelNearBubble();
                return true;
            case MotionEvent.ACTION_UP:
                bubble.setPressed(false);
                if (moved) snapToEdge(true);
                else bubble.performClick();
                return true;
            case MotionEvent.ACTION_CANCEL:
                bubble.setPressed(false);
                clampBubblePosition();
                IrisPrefs.setBubblePosition(this, bubbleParams.x, bubbleParams.y);
                if (bubble.getParent() != null) {
                    windowManager.updateViewLayout(bubble, bubbleParams);
                }
                return true;
            default:
                return false;
        }
    }

    private float distanceFromStart(MotionEvent event) {
        float x = event.getRawX() - touchX;
        float y = event.getRawY() - touchY;
        return (float) Math.sqrt((x * x) + (y * y));
    }

    private void clampBubblePosition() {
        if (bubbleParams == null) return;

        Rect bounds = bubbleMovementBounds();
        bubbleParams.x = Math.max(bounds.left, Math.min(bubbleParams.x, bounds.right));
        bubbleParams.y = Math.max(bounds.top, Math.min(bubbleParams.y, bounds.bottom));
    }

    private Rect bubbleMovementBounds() {
        int margin = IrisUi.dp(this, 6);
        int screenWidth = getResources().getDisplayMetrics().widthPixels;
        int screenHeight = getResources().getDisplayMetrics().heightPixels;
        int top = IrisUi.dp(this, 40);
        int bottom = IrisUi.dp(this, 24);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            WindowMetrics metrics = windowManager.getCurrentWindowMetrics();
            Insets insets = metrics.getWindowInsets().getInsetsIgnoringVisibility(
                WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout()
            );
            // Overlay gravity coordinates are relative to the system-bar-inset frame.
            screenWidth = metrics.getBounds().width() - insets.left - insets.right;
            screenHeight = metrics.getBounds().height() - insets.top - insets.bottom;
            top = margin;
            bottom = margin;
        }
        int maxX = Math.max(margin, screenWidth - bubbleParams.width - margin);
        int maxY = Math.max(top, screenHeight - bubbleParams.height - bottom);
        return new Rect(margin, top, maxX, maxY);
    }

    private void cancelSnap() {
        if (snapAnimator == null) return;
        snapAnimator.removeAllListeners();
        snapAnimator.removeAllUpdateListeners();
        snapAnimator.cancel();
        snapAnimator = null;
    }

    private void snapToEdge(boolean animate) {
        cancelSnap();
        if (bubble == null || bubbleParams == null || bubble.getParent() == null) return;
        clampBubblePosition();
        Rect bounds = bubbleMovementBounds();
        int targetX = bubbleParams.x - bounds.left <= bounds.right - bubbleParams.x ? bounds.left : bounds.right;
        if (!animate || !IrisMotion.animationsEnabled() || targetX == bubbleParams.x) {
            moveBubbleTo(targetX);
            IrisPrefs.setBubblePosition(this, bubbleParams.x, bubbleParams.y);
            return;
        }

        snapAnimator = ValueAnimator.ofInt(bubbleParams.x, targetX);
        snapAnimator.setDuration(220);
        snapAnimator.setInterpolator(new DecelerateInterpolator());
        snapAnimator.addUpdateListener(animation -> moveBubbleTo((int) animation.getAnimatedValue()));
        snapAnimator.addListener(new AnimatorListenerAdapter() {
            @Override
            public void onAnimationEnd(Animator animation) {
                snapAnimator = null;
                if (bubbleParams != null) IrisPrefs.setBubblePosition(OverlayService.this, bubbleParams.x, bubbleParams.y);
            }
        });
        snapAnimator.start();
    }

    private void moveBubbleTo(int x) {
        if (bubble == null || bubbleParams == null || bubble.getParent() == null) return;
        bubbleParams.x = x;
        clampBubblePosition();
        windowManager.updateViewLayout(bubble, bubbleParams);
        if (panel != null) positionPanelNearBubble();
    }

    @Override
    public void onConfigurationChanged(Configuration configuration) {
        super.onConfigurationChanged(configuration);
        snapToEdge(false);
    }

    private void handleBubbleTap() {
        if (state == STATE_SCANNING) {
            if (panel == null) showScanningPanel(currentInputType);
            else removePanelView();
            return;
        }

        if (state == STATE_RESULT && panel == null) {
            showResultPanel();
            return;
        }

        if (state == STATE_INPUT || state == STATE_RESULT || state == STATE_ERROR) {
            resetToIdle();
        } else {
            showInputPanel();
        }
    }

    private void showInputPanel() {
        state = STATE_INPUT;
        setBubbleActive(false);

        LinearLayout card = createPanelShell("PASTE TEXT", view -> resetToIdle());
        LinearLayout body = IrisUi.vertical(this, 16);
        body.addView(IrisUi.title(this, "Paste text to verify", 18), IrisUi.matchWrap());
        body.addView(
            IrisUi.muted(this, "Use this for Facebook posts that copy text without showing Android's selection menu.", 12.5f),
            IrisUi.spaced(this, 6)
        );

        claimInput = new EditText(this);
        claimInput.setTextColor(IrisUi.TEXT);
        claimInput.setHintTextColor(IrisUi.TEXT_LIGHT);
        claimInput.setTextSize(14);
        claimInput.setGravity(Gravity.TOP | Gravity.START);
        claimInput.setMinLines(4);
        claimInput.setMaxLines(7);
        claimInput.setSingleLine(false);
        claimInput.setImeOptions(EditorInfo.IME_ACTION_NONE);
        claimInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        claimInput.setHint("Paste Facebook post text or type a claim here");
        claimInput.setPadding(IrisUi.dp(this, 12), IrisUi.dp(this, 10), IrisUi.dp(this, 12), IrisUi.dp(this, 10));
        claimInput.setBackground(IrisUi.bordered(this, Color.WHITE, 14, IrisUi.BORDER));
        LinearLayout.LayoutParams inputParams = IrisUi.spaced(this, 12);
        inputParams.height = IrisUi.dp(this, 124);
        body.addView(claimInput, inputParams);

        Button paste = IrisUi.secondaryButton(this, "Paste from Clipboard");
        paste.setOnClickListener(view -> pasteClipboardIntoInput());
        body.addView(paste, IrisUi.spaced(this, 12));

        Button check = IrisUi.primaryButton(this, "Check with IRIS");
        check.setOnClickListener(view -> submitPastedText());
        body.addView(check, IrisUi.spaced(this, 8));

        panelStatus = IrisUi.muted(this, "Clipboard is read only when you tap Paste from Clipboard.", 11.5f);
        panelStatus.setGravity(Gravity.CENTER);
        body.addView(panelStatus, IrisUi.spaced(this, 8));

        Button chooseImage = IrisUi.secondaryButton(this, "Choose image for OCR");
        chooseImage.setOnClickListener(view -> openImagePicker());
        body.addView(chooseImage, IrisUi.spaced(this, 12));

        Button open = IrisUi.ghostButton(this, "Open full IRIS app");
        open.setOnClickListener(view -> {
            Intent launch = new Intent(this, MainActivity.class);
            launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(launch);
            resetToIdle();
        });
        body.addView(open, IrisUi.spaced(this, 12));

        Button turnOff = IrisUi.secondaryButton(this, "Turn off bubble");
        turnOff.setOnClickListener(view -> stopAndDisable());
        body.addView(turnOff, IrisUi.spaced(this, 10));

        card.addView(body, IrisUi.matchWrap());
        showPanelView(card, true, panelHeightEstimate());
        enterPasteTextState();
    }

    private void showScanningPanel(String type) {
        state = STATE_SCANNING;
        setBubbleActive(true);

        LinearLayout card = createPanelShell("SCANNING", view -> cancelActiveScan());
        LinearLayout body = IrisUi.vertical(this, 18);

        TextView title = IrisUi.title(this, "IRIS is scanning...", 19);
        title.setGravity(Gravity.CENTER);
        body.addView(title, IrisUi.matchWrap());

        IrisScanIndicator progressBar = new IrisScanIndicator(this);
        LinearLayout.LayoutParams progressParams = IrisUi.spaced(this, 16);
        progressParams.gravity = Gravity.CENTER_HORIZONTAL;
        body.addView(progressBar, progressParams);

        String preview = "image".equals(type)
            ? "Readable image text will be extracted, then checked by the shared IRIS pipeline."
            : truncate(currentFallbackText, 220);
        body.addView(scanPreview(preview, "image".equals(type)), IrisUi.spaced(this, 14));

        TextView detail = IrisUi.muted(
            this,
            "Checking VERA Files, Rappler, ABS-CBN, GMA, Inquirer, PhilStar, Manila Bulletin, PNA, PIA, DZRH, and OneNews.",
            12.5f
        );
        detail.setGravity(Gravity.CENTER);
        body.addView(detail, IrisUi.spaced(this, 8));

        card.addView(body, IrisUi.matchWrap());
        showPanelView(card, false, panelHeightEstimate());
    }

    private View scanPreview(String value, boolean image) {
        LinearLayout box = IrisUi.vertical(this, 12);
        box.setBackground(IrisUi.bordered(this, IrisUi.BLUE_BG, 14, Color.rgb(187, 218, 255)));
        box.addView(IrisUi.eyebrow(this, image ? "Image OCR" : "Selected text"), IrisUi.matchWrap());
        TextView text = IrisUi.text(this, value, 13.5f, IrisUi.TEXT, Typeface.NORMAL);
        text.setLineSpacing(0, 1.15f);
        box.addView(text, IrisUi.spaced(this, 5));
        return box;
    }

    private void showResultPanel() {
        if (resultData == null) {
            showErrorPanel("IRIS returned no readable result.");
            return;
        }

        state = STATE_RESULT;
        setBubbleActive(false);

        LinearLayout card = createPanelShell("VERIFICATION RESULT", view -> resetToIdle());
        LinearLayout body = IrisUi.vertical(this, 16);

        if (resultData.claims.isEmpty()) {
            body.addView(errorCard("IRIS did not return a readable result."), IrisUi.matchWrap());
        } else {
            body.addView(navigator(), IrisUi.matchWrap());
            body.addView(claimPanel(resultData.claims.get(claimIndex)), IrisUi.spaced(this, 12));
        }

        if (!resultData.skippedSegments.isEmpty()) {
            body.addView(skippedNote(), IrisUi.spaced(this, 12));
        }

        TextView disclaimer = IrisUi.muted(this, "IRIS is an assistant, not an authority. Always read the linked articles before sharing.", 11);
        disclaimer.setGravity(Gravity.CENTER);
        body.addView(disclaimer, IrisUi.spaced(this, 12));

        ScrollView scrollView = new ScrollView(this);
        scrollView.setFillViewport(false);
        scrollView.addView(body, IrisUi.matchWrap());
        LinearLayout.LayoutParams scrollParams = IrisUi.matchWrap();
        scrollParams.height = resultBodyHeight();
        card.addView(scrollView, scrollParams);
        showPanelView(card, false, resultPanelHeightEstimate());
    }

    private void showErrorPanel(String message) {
        state = STATE_ERROR;
        setBubbleActive(false);

        LinearLayout card = createPanelShell("CHECK FAILED", view -> resetToIdle());
        LinearLayout body = IrisUi.vertical(this, 16);
        body.addView(errorCard(TextUtils.isEmpty(message) ? "IRIS could not complete the check." : message), IrisUi.matchWrap());

        Button tryAgain = IrisUi.primaryButton(this, "Try another check");
        tryAgain.setOnClickListener(view -> showInputPanel());
        body.addView(tryAgain, IrisUi.spaced(this, 12));

        Button close = IrisUi.secondaryButton(this, "Close");
        close.setOnClickListener(view -> resetToIdle());
        body.addView(close, IrisUi.spaced(this, 8));

        card.addView(body, IrisUi.matchWrap());
        showPanelView(card, false, panelHeightEstimate());
    }

    private LinearLayout createPanelShell(String modeLabel, View.OnClickListener closeListener) {
        LinearLayout card = IrisUi.card(this, 0);
        card.setElevation(IrisUi.dp(this, 14));
        card.addView(panelHeader(modeLabel, closeListener), IrisUi.matchWrap());
        return card;
    }

    private View panelHeader(String label, View.OnClickListener closeListener) {
        LinearLayout header = IrisUi.horizontal(this, 12);
        header.setBackground(IrisUi.gradient(this, 20));

        FrameLayout markHolder = new FrameLayout(this);
        markHolder.setBackground(IrisUi.rounded(this, Color.WHITE, 999));
        IrisMarkView mark = new IrisMarkView(this);
        FrameLayout.LayoutParams markParams = new FrameLayout.LayoutParams(
            IrisUi.dp(this, 24),
            IrisUi.dp(this, 24),
            Gravity.CENTER
        );
        markHolder.addView(mark, markParams);
        header.addView(markHolder, IrisUi.fixed(this, 34, 34));

        LinearLayout copy = IrisUi.vertical(this, 0);
        TextView name = IrisUi.text(this, "IRIS", 18, Color.WHITE, Typeface.BOLD);
        name.setIncludeFontPadding(false);
        TextView ready = IrisUi.text(this, label, 10, Color.WHITE, Typeface.BOLD);
        ready.setAlpha(0.82f);
        ready.setLetterSpacing(0.1f);
        copy.addView(name, IrisUi.matchWrap());
        copy.addView(ready, IrisUi.matchWrap());

        LinearLayout.LayoutParams copyParams = IrisUi.rowWeight(1);
        copyParams.setMargins(IrisUi.dp(this, 8), 0, 0, 0);
        header.addView(copy, copyParams);

        Button close = new Button(this);
        close.setText("X");
        close.setTextColor(Color.WHITE);
        close.setTextSize(12);
        close.setAllCaps(false);
        close.setBackground(IrisUi.rounded(this, Color.argb(45, 255, 255, 255), 999));
        IrisUi.touchFeedback(close, 999);
        close.setOnClickListener(closeListener);
        header.addView(close, IrisUi.fixed(this, 36, 36));
        return header;
    }

    private void showPanelView(LinearLayout nextPanel, boolean focusable, int heightEstimate) {
        boolean attached = panel != null && panel.getParent() != null;
        if (!focusable) {
            hideKeyboard();
            claimInput = null;
            panelStatus = null;
        }
        if (attached) {
            // Keep the attached window across state changes, including the new input references.
            panel.removeAllViews();
            while (nextPanel.getChildCount() > 0) {
                View child = nextPanel.getChildAt(0);
                nextPanel.removeViewAt(0);
                panel.addView(child);
            }
        } else {
            panel = nextPanel;
        }
        panel.setFocusable(focusable);
        panel.setFocusableInTouchMode(focusable);
        panel.setOnKeyListener((view, keyCode, event) -> {
            if (keyCode == KeyEvent.KEYCODE_BACK && event.getAction() == KeyEvent.ACTION_UP) {
                resetToIdle();
                return true;
            }
            return false;
        });

        int flags = WindowManager.LayoutParams.FLAG_WATCH_OUTSIDE_TOUCH
            | WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL;
        if (!focusable) flags |= WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE;

        if (panelParams == null) {
            panelParams = new WindowManager.LayoutParams(
                panelWidthPx(),
                WindowManager.LayoutParams.WRAP_CONTENT,
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                flags,
                PixelFormat.TRANSLUCENT
            );
        }
        panelParams.flags = flags;
        panelParams.gravity = Gravity.TOP | Gravity.LEFT;
        panelParams.softInputMode = focusable
            ? WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE | WindowManager.LayoutParams.SOFT_INPUT_STATE_VISIBLE
            : WindowManager.LayoutParams.SOFT_INPUT_STATE_UNSPECIFIED;
        positionPanelNearBubble(heightEstimate);
        panel.setOnTouchListener((view, event) -> {
            if (event.getAction() == MotionEvent.ACTION_OUTSIDE) {
                if (state == STATE_SCANNING) {
                    removePanelView();
                } else {
                    resetToIdle();
                }
                return true;
            }
            return false;
        });

        if (!attached) windowManager.addView(panel, panelParams);
        panel.post(() -> positionPanelNearBubble(0));
    }

    private void positionPanelNearBubble() {
        positionPanelNearBubble(0);
    }

    private void positionPanelNearBubble(int heightEstimate) {
        if (panelParams == null || bubbleParams == null) return;

        int margin = IrisUi.dp(this, 12);
        int panelWidth = panelWidthPx();
        int panelHeight = panel != null && panel.getHeight() > 0 ? panel.getHeight() : heightEstimate;
        if (panelHeight <= 0) panelHeight = panelHeightEstimate();
        int screenWidth = getResources().getDisplayMetrics().widthPixels;
        int screenHeight = getResources().getDisplayMetrics().heightPixels;

        int bubbleCenter = bubbleParams.x + (bubbleParams.width / 2);
        int x = bubbleCenter - (panelWidth / 2);
        if (x + panelWidth > screenWidth - margin) x = screenWidth - panelWidth - margin;
        if (x < margin) x = margin;

        int above = bubbleParams.y - panelHeight - margin;
        int below = bubbleParams.y + bubbleParams.height + margin;
        int y = above >= margin ? above : below;
        if (y + panelHeight > screenHeight - margin) y = Math.max(margin, screenHeight - panelHeight - margin);
        if (y < margin) y = margin;

        panelParams.x = x;
        panelParams.y = y;
        panelParams.width = panelWidth;

        if (panel != null && panel.getParent() != null) {
            windowManager.updateViewLayout(panel, panelParams);
        }
    }

    private int panelWidthPx() {
        int margin = IrisUi.dp(this, 12);
        int preferredWidth = IrisUi.dp(this, 332);
        int availableWidth = getResources().getDisplayMetrics().widthPixels - (margin * 2);
        return availableWidth > 0 ? Math.min(preferredWidth, availableWidth) : preferredWidth;
    }

    private int panelHeightEstimate() {
        return IrisUi.dp(this, 440);
    }

    private int resultPanelHeightEstimate() {
        return IrisUi.dp(this, 590);
    }

    private int resultBodyHeight() {
        int available = getResources().getDisplayMetrics().heightPixels - IrisUi.dp(this, 190);
        return Math.max(IrisUi.dp(this, 360), Math.min(IrisUi.dp(this, 520), available));
    }

    private void enterPasteTextState() {
        if (windowManager == null || panel == null || panelParams == null) return;

        panelParams.flags = panelParams.flags & ~WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE;
        panelParams.softInputMode = WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE | WindowManager.LayoutParams.SOFT_INPUT_STATE_VISIBLE;
        if (panel.getParent() != null) {
            windowManager.updateViewLayout(panel, panelParams);
        }

        panel.requestFocus();
        if (claimInput != null) {
            EditText input = claimInput;
            input.post(() -> {
                if (input != claimInput || !input.isAttachedToWindow()) return;
                input.requestFocus();
                InputMethodManager inputMethodManager = (InputMethodManager) getSystemService(Context.INPUT_METHOD_SERVICE);
                if (inputMethodManager != null) {
                    inputMethodManager.showSoftInput(input, InputMethodManager.SHOW_IMPLICIT);
                }
            });
        }
    }

    private void exitPasteTextState() {
        hideKeyboard();
        if (windowManager == null || panel == null || panelParams == null) return;

        panelParams.flags = panelParams.flags | WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE;
        panelParams.softInputMode = WindowManager.LayoutParams.SOFT_INPUT_STATE_UNSPECIFIED;
        if (panel.getParent() != null) {
            windowManager.updateViewLayout(panel, panelParams);
        }
    }

    private void hideKeyboard() {
        if (panel == null) return;

        InputMethodManager inputMethodManager = (InputMethodManager) getSystemService(Context.INPUT_METHOD_SERVICE);
        if (inputMethodManager != null) {
            inputMethodManager.hideSoftInputFromWindow(panel.getWindowToken(), 0);
        }
    }

    private void pasteClipboardIntoInput() {
        String pasted = pasteFromClipboard();
        if (pasted == null || pasted.trim().isEmpty()) {
            setPanelStatus("Clipboard does not contain readable text yet.", Color.rgb(153, 27, 27));
            return;
        }

        String text = pasted.trim();
        claimInput.setText(text);
        claimInput.setSelection(claimInput.getText().length());
        setPanelStatus("Text pasted. Tap Check with IRIS when ready.", IrisUi.GREEN);
    }

    private String pasteFromClipboard() {
        try {
            ClipboardManager clipboard = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
            if (clipboard == null || !clipboard.hasPrimaryClip()) return null;

            ClipData clip = clipboard.getPrimaryClip();
            if (clip == null || clip.getItemCount() == 0) return null;

            CharSequence text = clip.getItemAt(0).coerceToText(this);
            return text == null ? null : text.toString();
        } catch (Exception error) {
            return null;
        }
    }

    private void submitPastedText() {
        String text = claimInput == null ? "" : claimInput.getText().toString().trim();
        if (text.isEmpty()) {
            setPanelStatus("Paste or type claim text before checking.", Color.rgb(153, 27, 27));
            return;
        }
        verifyTextSource(text);
    }

    private void openImagePicker() {
        removePanelView();
        state = STATE_IDLE;
        setBubbleActive(false);
        Intent picker = new Intent(this, PickImageActivity.class);
        picker.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        startActivity(picker);
    }

    private void verifyTextSource(String rawText) {
        String text = rawText == null ? "" : rawText.trim();
        if (text.isEmpty()) {
            showErrorPanel("No selected text was provided.");
            return;
        }

        currentInputType = "text";
        currentFallbackText = text;
        long token = ++requestToken;
        showScanningPanel("text");

        IrisApiClient.verifyText(this, text, new IrisApiClient.Callback() {
            @Override
            public void onSuccess(String responseJson) {
                if (token != requestToken) return;
                resultData = IrisResultData.parse(responseJson, currentFallbackText, currentInputType);
                claimIndex = 0;
                showResultPanel();
            }

            @Override
            public void onError(String message) {
                if (token != requestToken) return;
                showErrorPanel(message);
            }
        });
    }

    private void verifyImageSource(Uri imageUri) {
        if (imageUri == null) {
            showErrorPanel("No shared image was provided.");
            return;
        }

        currentInputType = "image";
        currentFallbackText = "Image selected for OCR.";
        long token = ++requestToken;
        showScanningPanel("image");

        IrisApiClient.verifyImageUri(this, imageUri, new IrisApiClient.Callback() {
            @Override
            public void onSuccess(String responseJson) {
                if (token != requestToken) return;
                resultData = IrisResultData.parse(responseJson, currentFallbackText, currentInputType);
                claimIndex = 0;
                showResultPanel();
            }

            @Override
            public void onError(String message) {
                if (token != requestToken) return;
                showErrorPanel(message);
            }
        });
    }

    private void cancelActiveScan() {
        requestToken += 1;
        resetToIdle();
    }

    private void setPanelStatus(String message, int color) {
        if (panelStatus == null) return;
        panelStatus.setText(message);
        panelStatus.setTextColor(color);
    }

    private void setBubbleActive(boolean active) {
        if (bubble != null) {
            bubble.setActive(active);
            bubble.setElevation(IrisUi.dp(this, active ? 18 : 12));
        }
    }

    private View navigator() {
        LinearLayout row = IrisUi.horizontal(this, 0);
        row.setGravity(Gravity.CENTER);

        int total = resultData == null ? 0 : resultData.claims.size();
        Button previous = roundNavButton("<");
        previous.setEnabled(claimIndex > 0);
        previous.setAlpha(claimIndex > 0 ? 1f : 0.35f);
        previous.setOnClickListener(view -> {
            claimIndex = Math.max(0, claimIndex - 1);
            showResultPanel();
        });
        row.addView(previous, IrisUi.fixed(this, 44, 44));

        TextView label = IrisUi.text(this, "Claim " + (claimIndex + 1) + " of " + total, 16, IrisUi.TEXT, Typeface.BOLD);
        label.setGravity(Gravity.CENTER);
        row.addView(label, IrisUi.rowWeight(1));

        Button next = roundNavButton(">");
        next.setEnabled(resultData != null && claimIndex < resultData.claims.size() - 1);
        next.setAlpha(next.isEnabled() ? 1f : 0.35f);
        next.setOnClickListener(view -> {
            if (resultData == null) return;
            claimIndex = Math.min(resultData.claims.size() - 1, claimIndex + 1);
            showResultPanel();
        });
        row.addView(next, IrisUi.fixed(this, 44, 44));
        return row;
    }

    private Button roundNavButton(String label) {
        Button button = new Button(this);
        button.setText(label);
        button.setTextSize(19);
        button.setTextColor(IrisUi.VIOLET);
        button.setAllCaps(false);
        button.setBackground(IrisUi.bordered(this, Color.WHITE, 999, IrisUi.BORDER));
        IrisUi.touchFeedback(button, 999);
        return button;
    }

    private View claimPanel(IrisResultData.ClaimItem claim) {
        LinearLayout wrapper = IrisUi.vertical(this, 0);
        wrapper.addView(claimBox(claim.claimText), IrisUi.matchWrap());

        if (claim.politicallySensitive) {
            wrapper.addView(politicalFlag(), IrisUi.spaced(this, 10));
        }

        wrapper.addView(verdictCard(claim), IrisUi.spaced(this, 10));
        wrapper.addView(evidenceSummary(claim), IrisUi.spaced(this, 10));
        wrapper.addView(IrisUi.eyebrow(this, "Evidence Sources"), IrisUi.spaced(this, 10));

        if (claim.sources.isEmpty()) {
            TextView empty = IrisUi.muted(this, "No valid evidence link found.", 12.5f);
            empty.setGravity(Gravity.CENTER);
            empty.setPadding(IrisUi.dp(this, 12), IrisUi.dp(this, 13), IrisUi.dp(this, 12), IrisUi.dp(this, 13));
            empty.setBackground(IrisUi.bordered(this, IrisUi.GRAY_BG, 14, IrisUi.GRAY_BORDER));
            wrapper.addView(empty, IrisUi.spaced(this, 8));
        } else {
            for (IrisResultData.SourceItem source : claim.sources) {
                wrapper.addView(sourceCard(source), IrisUi.spaced(this, 8));
            }
        }

        return wrapper;
    }

    private View claimBox(String claimText) {
        LinearLayout box = IrisUi.horizontal(this, 0);
        box.setGravity(Gravity.CENTER_VERTICAL);
        box.setBackground(IrisUi.bordered(this, IrisUi.BLUE_BG, 14, Color.rgb(187, 218, 255)));

        View accent = new View(this);
        accent.setBackgroundColor(IrisUi.BLUE_BORDER);
        box.addView(accent, new LinearLayout.LayoutParams(IrisUi.dp(this, 4), LinearLayout.LayoutParams.MATCH_PARENT));

        LinearLayout copy = IrisUi.vertical(this, 12);
        if ("image".equals(currentInputType)) {
            copy.addView(IrisUi.eyebrow(this, "Text extracted from image"), IrisUi.matchWrap());
        }

        TextView quote = new TextView(this);
        quote.setText(TextUtils.isEmpty(claimText) ? "No claim text returned." : claimText);
        quote.setTextColor(IrisUi.TEXT);
        quote.setTextSize(15.5f);
        quote.setTypeface(Typeface.SERIF, Typeface.ITALIC);
        quote.setLineSpacing(0, 1.12f);
        copy.addView(quote, IrisUi.matchWrap());
        box.addView(copy, IrisUi.rowWeight(1));
        return box;
    }

    private View politicalFlag() {
        LinearLayout flag = IrisUi.horizontal(this, 11);
        flag.setBackground(IrisUi.bordered(this, IrisUi.ORANGE_BG, 14, IrisUi.ORANGE_BORDER));

        TextView icon = new TextView(this);
        icon.setText("!");
        icon.setTextSize(17);
        icon.setGravity(Gravity.CENTER);
        icon.setTextColor(IrisUi.ORANGE);
        icon.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        icon.setBackground(IrisUi.rounded(this, Color.WHITE, 999));
        flag.addView(icon, IrisUi.fixed(this, 32, 32));

        LinearLayout copy = IrisUi.vertical(this, 0);
        copy.addView(IrisUi.text(this, "Politically Sensitive", 13.5f, IrisUi.ORANGE, Typeface.BOLD), IrisUi.matchWrap());
        copy.addView(IrisUi.text(this, "Apply extra scrutiny before sharing.", 11.5f, IrisUi.ORANGE, Typeface.NORMAL), IrisUi.matchWrap());
        flag.addView(copy, IrisUi.rowWeight(1));
        return flag;
    }

    private View verdictCard(IrisResultData.ClaimItem claim) {
        LinearLayout card = IrisUi.horizontal(this, 13);
        int color = IrisUi.verdictColor(claim.verdict);
        card.setBackground(IrisUi.bordered(this, IrisUi.verdictBackground(claim.verdict), 14, IrisUi.verdictBorder(claim.verdict)));

        TextView icon = new TextView(this);
        icon.setText(IrisUi.verdictIcon(claim.verdict));
        icon.setTextSize(17);
        icon.setTextColor(color);
        icon.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        icon.setGravity(Gravity.CENTER);
        card.addView(icon, IrisUi.fixed(this, 40, 40));

        LinearLayout copy = IrisUi.vertical(this, 0);
        copy.addView(IrisUi.text(this, claim.verdict, 17, color, Typeface.BOLD), IrisUi.matchWrap());
        copy.addView(IrisUi.text(this, claim.message, 13, color, Typeface.NORMAL), IrisUi.matchWrap());
        card.addView(copy, IrisUi.rowWeight(1));
        return card;
    }

    private View evidenceSummary(IrisResultData.ClaimItem claim) {
        LinearLayout row = IrisUi.horizontal(this, 0);

        TextView pill = new TextView(this);
        pill.setText(claim.evidenceCount + " of " + claim.evidenceTotal);
        pill.setTextColor(Color.WHITE);
        pill.setTextSize(12.5f);
        pill.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        pill.setGravity(Gravity.CENTER);
        pill.setBackground(IrisUi.gradient(this, 999));
        row.addView(pill, IrisUi.fixed(this, 74, 32));

        TextView label = IrisUi.muted(this, claim.evidenceCount == 1 ? " evidence source used" : " evidence sources used", 12.5f);
        row.addView(label, IrisUi.rowWeight(1));
        return row;
    }

    private View sourceCard(IrisResultData.SourceItem source) {
        LinearLayout card = IrisUi.vertical(this, 11);
        card.setBackground(IrisUi.bordered(this, Color.WHITE, 14, IrisUi.BORDER));
        card.setClickable(true);
        IrisUi.touchFeedback(card, 14);
        card.setOnClickListener(view -> {
            Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(source.url));
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(intent);
        });

        LinearLayout meta = IrisUi.horizontal(this, 0);
        meta.addView(IrisUi.text(this, source.outlet, 11.5f, IrisUi.VIOLET, Typeface.BOLD), IrisUi.rowWeight(1));
        TextView date = IrisUi.muted(this, source.date, 10.5f);
        date.setGravity(Gravity.END);
        meta.addView(date, IrisUi.rowWeight(1));
        card.addView(meta, IrisUi.matchWrap());

        TextView title = IrisUi.text(this, source.title, 13, IrisUi.TEXT, Typeface.BOLD);
        card.addView(title, IrisUi.spaced(this, 5));

        TextView link = IrisUi.text(this, "Read full article", 11.5f, IrisUi.VIOLET, Typeface.BOLD);
        card.addView(link, IrisUi.spaced(this, 5));
        return card;
    }

    private View skippedNote() {
        StringBuilder message = new StringBuilder("IRIS skipped ");
        for (int index = 0; index < resultData.skippedSegments.size(); index += 1) {
            IrisResultData.SkippedSegment segment = resultData.skippedSegments.get(index);
            if (index > 0) message.append(index == resultData.skippedSegments.size() - 1 ? " and " : ", ");
            message.append(segment.count).append(" ").append(segment.label);
            if (segment.count != 1) message.append("s");
        }
        message.append(" because they were not independently checkable.");

        TextView note = IrisUi.muted(this, message.toString(), 12);
        note.setGravity(Gravity.CENTER);
        note.setPadding(IrisUi.dp(this, 12), IrisUi.dp(this, 12), IrisUi.dp(this, 12), IrisUi.dp(this, 12));
        note.setBackground(IrisUi.bordered(this, IrisUi.GRAY_BG, 14, IrisUi.GRAY_BORDER));
        return note;
    }

    private View errorCard(String message) {
        TextView error = IrisUi.text(this, message, 13.5f, Color.rgb(153, 27, 27), Typeface.BOLD);
        error.setPadding(IrisUi.dp(this, 16), IrisUi.dp(this, 14), IrisUi.dp(this, 16), IrisUi.dp(this, 14));
        error.setBackground(IrisUi.bordered(this, Color.rgb(254, 242, 242), 14, Color.rgb(252, 165, 165)));
        return error;
    }

    private void removePanelView() {
        if (state == STATE_INPUT) {
            exitPasteTextState();
        } else {
            hideKeyboard();
        }

        if (windowManager != null && panel != null && panel.getParent() != null) {
            windowManager.removeView(panel);
        }
        panel = null;
        claimInput = null;
        panelStatus = null;
        panelParams = null;
    }

    private void resetToIdle() {
        if (state == STATE_SCANNING) requestToken += 1;
        removePanelView();
        state = STATE_IDLE;
        claimIndex = 0;
        resultData = null;
        currentFallbackText = "";
        currentInputType = "text";
        setBubbleActive(false);
    }

    private void stopAndDisable() {
        cancelSnap();
        resetToIdle();
        IrisPrefs.setBubbleEnabled(this, false);
        if (windowManager != null && bubble != null && bubble.getParent() != null) {
            windowManager.removeView(bubble);
        }
        bubble = null;
        bubbleParams = null;
        stopForegroundCompat();
        stopSelf();
    }

    private void showActiveNotification() {
        NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (manager == null) return;

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                NOTIFICATION_CHANNEL_ID,
                "IRIS Bubble",
                NotificationManager.IMPORTANCE_LOW
            );
            channel.setDescription("Shows when the IRIS floating bubble is active.");
            manager.createNotificationChannel(channel);
        }

        Intent stopIntent = new Intent(this, OverlayService.class);
        stopIntent.setAction(ACTION_STOP);
        PendingIntent stopPendingIntent = PendingIntent.getService(
            this,
            8202,
            stopIntent,
            PendingIntent.FLAG_UPDATE_CURRENT | immutableFlag()
        );

        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
            ? new Notification.Builder(this, NOTIFICATION_CHANNEL_ID)
            : new Notification.Builder(this);
        builder
            .setSmallIcon(R.drawable.iris_logo_mark)
            .setContentTitle("IRIS is active")
            .setContentText("Tap to disable")
            .setOngoing(true)
            .setContentIntent(stopPendingIntent);

        try {
            startForeground(NOTIFICATION_ID, builder.build());
        } catch (Exception error) {
            manager.notify(NOTIFICATION_ID, builder.build());
        }
    }

    private int immutableFlag() {
        return Build.VERSION.SDK_INT >= Build.VERSION_CODES.M ? PendingIntent.FLAG_IMMUTABLE : 0;
    }

    private void stopForegroundCompat() {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                stopForeground(STOP_FOREGROUND_REMOVE);
            } else {
                stopForeground(true);
            }
        } catch (Exception ignored) {
        }

        NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (manager != null) {
            manager.cancel(NOTIFICATION_ID);
        }
    }

    private String truncate(String value, int maxLength) {
        if (value == null) return "";
        return value.length() > maxLength ? value.substring(0, Math.max(0, maxLength - 3)) + "..." : value;
    }

    @Override
    public void onDestroy() {
        cancelSnap();
        requestToken += 1;
        super.onDestroy();
        removePanelView();
        if (windowManager != null && bubble != null && bubble.getParent() != null) {
            windowManager.removeView(bubble);
        }
        bubble = null;
        IrisPrefs.setBubbleEnabled(this, false);
        stopForegroundCompat();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
