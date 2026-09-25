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
import android.os.SystemClock;
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

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.List;
import java.util.Locale;

public class OverlayService extends Service {
    public static final String ACTION_SHOW = "com.iris.app.action.SHOW_BUBBLE";
    public static final String ACTION_STOP = "com.iris.app.action.STOP_BUBBLE";
    public static final String ACTION_VERIFY_TEXT = "com.iris.app.action.VERIFY_TEXT";
    public static final String ACTION_VERIFY_IMAGE_URI = "com.iris.app.action.VERIFY_IMAGE_URI";
    public static final String EXTRA_TEXT = "extra_text";
    public static final String EXTRA_IMAGE_URI = "extra_image_uri";

    private static final String NOTIFICATION_CHANNEL_ID = "iris_bubble";
    private static final int NOTIFICATION_ID = 8201;
    // A tap on the bubble while the panel is open arrives twice: once as ACTION_OUTSIDE on
    // the panel, which closes it, and again as a click on the bubble, which would open it
    // straight back up. The second half of that gesture is ignored.
    private static final long BUBBLE_REOPEN_GUARD_MS = 400;

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
    private long panelDismissedAt;
    private String pendingError;
    private long requestToken;
    private IrisResultData resultData;
    private int claimIndex;
    private String currentFallbackText = "";
    private String currentInputType = "text";
    private int restingBubbleX = -1;
    private int restingBubbleY = -1;
    private boolean isAnchoredToUpperRight = false;
    // Where an in-flight bubble animation was heading when a touch froze it. A later tap
    // finishes the journey from here, so an interrupted return can never strand the bubble
    // part-way home and get remembered as the resting position.
    private boolean animationPending = false;
    private int pendingTargetX;
    private int pendingTargetY;
    private Runnable pendingEnd;
    // The input panel opens with its three rarely-used actions folded away, so it never
    // claims the whole screen. Remembered for this service session only.
    private boolean quickActionsExpanded = false;
    // Recent checks folds for the same reason quick actions do: the input panel's job is
    // starting a check, and a glance backward is a choice, not a requirement.
    private boolean recentChecksExpanded = false;
    // The one expanded detail in the recent checks list, so opening another row or
    // folding the section can always reach the open one from a single place.
    private final OpenDetailTracker openRecentDetail = new OpenDetailTracker(this::repositionPanelForDetail);
    // Set when the user asks to see every source; cleared when a new result or a new claim
    // arrives, so each verdict starts from the same collapsed three-source default.
    private boolean sourcesExpanded = false;
    private final SimpleDateFormat historyDateFormat = new SimpleDateFormat("MM-dd HH:mm", Locale.getDefault());

    @Override
    public void onCreate() {
        super.onCreate();
        applyOverlayTheme();
        windowManager = (WindowManager) getSystemService(WINDOW_SERVICE);
    }

    /**
     * Swaps the palette at every overlay build instead of restarting the service to pick
     * up a theme change: a restart runs onDestroy, which marks the bubble disabled and
     * could strand it. The palette is process-wide, so only the visible bubble needs the
     * invalidate.
     */
    private void applyOverlayTheme() {
        IrisUi.applyTheme(this);
        if (bubble != null) bubble.invalidate();
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
        // Reached on every ACTION_SHOW, so this is also the repaint path after the
        // in-app theme selector runs.
        applyOverlayTheme();
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
            if (animationPending && !IrisMotion.animationsEnabled()) settleAnimation();
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
                if (isAnchoredToUpperRight) {
                    isAnchoredToUpperRight = false;
                    if (panel != null && panel.getParent() != null) {
                        if (state == STATE_SCANNING || state == STATE_RESULT) hidePanel();
                        else resetToIdle();
                    }
                }
                bubbleParams.x = startX + (int) (event.getRawX() - touchX);
                bubbleParams.y = startY + (int) (event.getRawY() - touchY);
                clampBubblePosition();
                windowManager.updateViewLayout(bubble, bubbleParams);
                if (panel != null) positionPanelNearBubble();
                return true;
            case MotionEvent.ACTION_UP:
                bubble.setPressed(false);
                if (moved) {
                    snapToEdge(true);
                } else {
                    // A tap finishes whatever return or snap a previous touch froze, so the
                    // bubble lands home before the click decides whether to reopen the panel.
                    settleAnimation();
                    bubble.performClick();
                }
                return true;
            case MotionEvent.ACTION_CANCEL:
                bubble.setPressed(false);
                if (moved) {
                    // The gesture was taken over mid-drag; the position the finger reached wins.
                    cancelSnap();
                    animationPending = false;
                    pendingEnd = null;
                    clampBubblePosition();
                    IrisPrefs.setBubblePosition(this, bubbleParams.x, bubbleParams.y);
                    if (bubble.getParent() != null) {
                        windowManager.updateViewLayout(bubble, bubbleParams);
                    }
                } else if (!settleAnimation()) {
                    clampBubblePosition();
                    IrisPrefs.setBubblePosition(this, bubbleParams.x, bubbleParams.y);
                    if (bubble.getParent() != null) {
                        windowManager.updateViewLayout(bubble, bubbleParams);
                    }
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
            moveBubbleTo(targetX, bubbleParams.y);
            IrisPrefs.setBubblePosition(this, bubbleParams.x, bubbleParams.y);
            return;
        }

        animateBubbleTo(targetX, bubbleParams.y, () -> {
            if (bubbleParams != null) {
                IrisPrefs.setBubblePosition(OverlayService.this, bubbleParams.x, bubbleParams.y);
            }
        });
    }

    /**
     * Lands an interrupted bubble animation on its destination instead of leaving it frozen
     * wherever the interrupting touch caught it.
     *
     * A tap that cancelled the return-to-resting animation used to strand the bubble part-way
     * home; the reopen guard then swallowed the tap, and that half-finished spot is what the
     * next anchor remembered as home. Finishing the journey here keeps one meaning of "home".
     *
     * @return whether an animation was actually waiting to be finished.
     */
    private boolean settleAnimation() {
        if (!animationPending) return false;

        int targetX = pendingTargetX;
        int targetY = pendingTargetY;
        Runnable onEnd = pendingEnd;
        cancelSnap();
        animationPending = false;
        pendingEnd = null;
        moveBubbleTo(targetX, targetY);
        if (onEnd != null) onEnd.run();
        return true;
    }

    private void animateBubbleTo(int targetX, int targetY, Runnable onEnd) {
        cancelSnap();
        animationPending = false;
        pendingEnd = null;
        if (bubble == null || bubbleParams == null || bubble.getParent() == null) {
            if (onEnd != null) onEnd.run();
            return;
        }

        if (!IrisMotion.animationsEnabled() || (bubbleParams.x == targetX && bubbleParams.y == targetY)) {
            moveBubbleTo(targetX, targetY);
            if (onEnd != null) onEnd.run();
            return;
        }

        pendingTargetX = targetX;
        pendingTargetY = targetY;
        pendingEnd = onEnd;
        animationPending = true;

        final int startX = bubbleParams.x;
        final int startY = bubbleParams.y;
        ValueAnimator animator = ValueAnimator.ofFloat(0f, 1f);
        animator.setDuration(220);
        animator.setInterpolator(new DecelerateInterpolator());
        animator.addUpdateListener(animation -> {
            float fraction = (float) animation.getAnimatedValue();
            int curX = (int) (startX + (targetX - startX) * fraction);
            int curY = (int) (startY + (targetY - startY) * fraction);
            moveBubbleTo(curX, curY);
        });
        animator.addListener(new AnimatorListenerAdapter() {
            @Override
            public void onAnimationEnd(Animator animation) {
                snapAnimator = null;
                animationPending = false;
                pendingEnd = null;
                moveBubbleTo(targetX, targetY);
                if (onEnd != null) onEnd.run();
            }
        });
        snapAnimator = animator;
        animator.start();
    }

    private void anchorBubbleToUpperRight(Runnable onEnd) {
        // A frozen return must land first, or the coordinates captured below as "home"
        // are the mid-flight spot the interrupted animation happened to be resting on.
        settleAnimation();

        if (!isAnchoredToUpperRight) {
            restingBubbleX = bubbleParams != null ? bubbleParams.x : -1;
            restingBubbleY = bubbleParams != null ? bubbleParams.y : -1;
            isAnchoredToUpperRight = true;
        }

        Rect bounds = bubbleMovementBounds();
        int targetX = bounds.right;
        int targetY = bounds.top;

        if (bubbleParams != null && bubbleParams.x == targetX && bubbleParams.y == targetY) {
            if (onEnd != null) onEnd.run();
            return;
        }

        animateBubbleTo(targetX, targetY, onEnd);
    }

    private void returnBubbleToRestingPosition() {
        if (!isAnchoredToUpperRight) return;
        isAnchoredToUpperRight = false;

        Rect bounds = bubbleMovementBounds();
        int targetX = restingBubbleX != -1 ? restingBubbleX : bounds.right;
        int targetY = restingBubbleY != -1 ? restingBubbleY : bounds.bottom;

        targetX = Math.max(bounds.left, Math.min(targetX, bounds.right));
        targetY = Math.max(bounds.top, Math.min(targetY, bounds.bottom));

        animateBubbleTo(targetX, targetY, () -> {
            if (bubbleParams != null) {
                IrisPrefs.setBubblePosition(OverlayService.this, bubbleParams.x, bubbleParams.y);
            }
        });
    }

    private void moveBubbleTo(int x, int y) {
        if (bubble == null || bubbleParams == null || bubble.getParent() == null) return;
        bubbleParams.x = x;
        bubbleParams.y = y;
        clampBubblePosition();
        windowManager.updateViewLayout(bubble, bubbleParams);
    }

    private void moveBubbleTo(int x) {
        if (bubbleParams != null) {
            moveBubbleTo(x, bubbleParams.y);
        }
    }

    @Override
    public void onConfigurationChanged(Configuration configuration) {
        super.onConfigurationChanged(configuration);
        // The system night setting can flip while the overlay is up; the panel rebuilds
        // on its next open, and the bubble repaints here.
        applyOverlayTheme();
        if (isAnchoredToUpperRight) {
            Rect bounds = bubbleMovementBounds();
            moveBubbleTo(bounds.right, bounds.top);
            if (panel != null && panel.getParent() != null) {
                positionPanelNearBubble();
            }
        } else {
            settleAnimation();
            snapToEdge(false);
        }
    }

    private void handleBubbleTap() {
        // The panel has just closed itself because this same tap landed outside it. Opening it
        // again here is what made the panel look like it refused to be put away.
        if (SystemClock.uptimeMillis() - panelDismissedAt < BUBBLE_REOPEN_GUARD_MS) return;

        // If the panel is currently open and the user clicks the floating bubble, close the panel
        // and return the bubble to its resting position.
        if (panel != null && panel.getParent() != null) {
            if (state == STATE_SCANNING || state == STATE_RESULT) {
                hidePanel();
            } else {
                resetToIdle();
            }
            return;
        }

        // Scanning and results are both worth keeping, so the bubble hides and shows them
        // rather than ending them. A check that is running keeps running.
        if (state == STATE_SCANNING) {
            showScanningPanel(currentInputType);
            return;
        }

        if (state == STATE_RESULT) {
            showResultPanel();
            return;
        }

        if (state == STATE_ERROR) {
            showErrorPanel(pendingError);
            return;
        }

        if (state == STATE_INPUT) {
            resetToIdle();
        } else {
            showInputPanel();
        }
    }

    /**
     * Puts the panel away without ending what it was showing.
     *
     * The state and any result stay as they are, so tapping the bubble brings the same panel
     * back. Only resetToIdle throws the result away, and only a button says to do that.
     */
    private void hidePanel() {
        removePanelView();
        returnBubbleToRestingPosition();
        // A result put away is still a result waiting to be read, so the bubble goes on
        // saying so. A scan put away keeps pulsing instead, which says the same thing.
        setBubbleReady(state == STATE_RESULT || state == STATE_ERROR);
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
        claimInput.setBackground(IrisUi.bordered(this, IrisUi.CARD, 14, IrisUi.BORDER));
        IrisUi.focusRing(claimInput, 14);
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

        View recent = recentChecksSection();
        if (recent != null) {
            body.addView(recent, IrisUi.spaced(this, 12));
        }

        body.addView(quickActionsSection(), IrisUi.spaced(this, 12));

        ScrollView scrollView = new ScrollView(this);
        scrollView.setFillViewport(false);
        scrollView.addView(body, IrisUi.matchWrap());
        card.addView(scrollView, IrisUi.matchWrap());
        showPanelView(card, true, panelHeightEstimate());
        enterPasteTextState();
    }

    /**
     * The three panel actions most opens never need, behind one foldable row.
     *
     * Collapsed by default so the input panel stays short enough to see the screen behind it;
     * the choice lasts for this service session, so a repeated open does not re-fold itself
     * under the user's finger.
     */
    private View quickActionsSection() {
        LinearLayout section = IrisUi.vertical(this, 12);
        section.setBackground(IrisUi.bordered(this, IrisUi.BG, 14, IrisUi.BORDER));

        LinearLayout header = IrisUi.horizontal(this, 0);
        header.setClickable(true);
        IrisUi.touchFeedback(header, 10);

        TextView label = IrisUi.text(this, "Quick actions", 13.5f, IrisUi.TEXT, Typeface.BOLD);
        TextView chevron = IrisUi.text(this, quickActionsExpanded ? "▾" : "▸", 15, IrisUi.VIOLET, Typeface.BOLD);
        chevron.setGravity(Gravity.CENTER_VERTICAL | Gravity.END);
        header.addView(label, IrisUi.rowWeight(1));
        header.addView(chevron, IrisUi.fixed(this, 28, 28));
        section.addView(header, IrisUi.matchWrap());

        LinearLayout actions = IrisUi.vertical(this, 0);

        Button chooseImage = IrisUi.secondaryButton(this, "Choose image for OCR");
        chooseImage.setOnClickListener(view -> openImagePicker());
        actions.addView(chooseImage, IrisUi.matchWrap());

        Button open = IrisUi.ghostButton(this, "Open full IRIS app");
        open.setOnClickListener(view -> {
            Intent launch = new Intent(this, MainActivity.class);
            launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(launch);
            resetToIdle();
        });
        actions.addView(open, IrisUi.spaced(this, 10));

        Button turnOff = IrisUi.secondaryButton(this, "Turn off bubble");
        turnOff.setOnClickListener(view -> stopAndDisable());
        actions.addView(turnOff, IrisUi.spaced(this, 10));

        actions.setVisibility(quickActionsExpanded ? View.VISIBLE : View.GONE);
        section.addView(actions, IrisUi.matchWrap());

        header.setOnClickListener(view -> {
            quickActionsExpanded = !quickActionsExpanded;
            actions.setVisibility(quickActionsExpanded ? View.VISIBLE : View.GONE);
            chevron.setText(quickActionsExpanded ? "▾" : "▸");
            // Release any capped height first, so the window is free to shrink with the
            // section instead of holding the taller measurement from before the fold.
            if (panelParams != null) {
                panelParams.height = WindowManager.LayoutParams.WRAP_CONTENT;
            }
            positionPanelNearBubble(0);
            if (panel != null) panel.post(() -> positionPanelNearBubble(0));
        });
        return section;
    }

    /**
     * Up to three past checks behind one foldable row, so the panel can offer a glance
     * backward without becoming a database browser. No stored checks means no section at
     * all: a header promising history that does not exist is noise.
     */
    private View recentChecksSection() {
        List<HistoryStore.HistoryEntry> entries = HistoryStore.recent(this, 3);
        if (entries.isEmpty()) return null;

        LinearLayout section = IrisUi.vertical(this, 12);
        section.setBackground(IrisUi.bordered(this, IrisUi.BG, 14, IrisUi.BORDER));

        LinearLayout header = IrisUi.horizontal(this, 0);
        header.setClickable(true);
        IrisUi.touchFeedback(header, 10);

        TextView label = IrisUi.text(this, "Recent checks", 13.5f, IrisUi.TEXT, Typeface.BOLD);
        TextView chevron = IrisUi.text(this, recentChecksExpanded ? "▾" : "▸", 15, IrisUi.VIOLET, Typeface.BOLD);
        chevron.setGravity(Gravity.CENTER_VERTICAL | Gravity.END);
        header.addView(label, IrisUi.rowWeight(1));
        header.addView(chevron, IrisUi.fixed(this, 28, 28));
        section.addView(header, IrisUi.matchWrap());

        LinearLayout list = IrisUi.vertical(this, 0);
        for (HistoryStore.HistoryEntry entry : entries) {
            list.addView(recentRow(entry), IrisUi.spaced(this, 8));
        }

        Button seeAll = IrisUi.ghostButton(this, "See all history");
        seeAll.setOnClickListener(view -> {
            resetToIdle();
            Intent launch = new Intent(this, HistoryActivity.class);
            launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(launch);
        });
        list.addView(seeAll, IrisUi.spaced(this, 8));

        list.setVisibility(recentChecksExpanded ? View.VISIBLE : View.GONE);
        section.addView(list, IrisUi.matchWrap());

        header.setOnClickListener(view -> {
            recentChecksExpanded = !recentChecksExpanded;
            list.setVisibility(recentChecksExpanded ? View.VISIBLE : View.GONE);
            chevron.setText(recentChecksExpanded ? "▾" : "▸");
            if (!recentChecksExpanded) {
                // Folding the list takes an open verdict with it, so a re-open starts clean.
                openRecentDetail.close();
            }
            // Release any capped height first, so the window is free to shrink with the
            // section instead of holding the taller measurement from before the fold.
            if (panelParams != null) {
                panelParams.height = WindowManager.LayoutParams.WRAP_CONTENT;
            }
            positionPanelNearBubble(0);
            if (panel != null) panel.post(() -> positionPanelNearBubble(0));
        });
        return section;
    }

    private View recentRow(HistoryStore.HistoryEntry entry) {
        // The detail lives in the same cell as the row, inside the panel's scrolling
        // body, so opening a check never leaves the panel or widens the window.
        LinearLayout cell = IrisUi.vertical(this, 0);
        LinearLayout detail = IrisUi.vertical(this, 0);
        detail.setVisibility(View.GONE);
        String checkedAt = historyDateFormat.format(new Date(entry.checkedAt));

        LinearLayout row = IrisUi.horizontal(this, 10);
        row.setClickable(true);
        IrisUi.touchFeedback(row, 12);
        row.setBackground(IrisUi.bordered(
            this,
            IrisUi.verdictBackground(entry.verdict),
            12,
            IrisUi.verdictBorder(entry.verdict)
        ));

        int color = IrisUi.verdictColor(entry.verdict);
        TextView icon = new TextView(this);
        icon.setText(IrisUi.verdictIcon(entry.verdict));
        icon.setTextSize(13);
        icon.setTextColor(color);
        icon.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        icon.setGravity(Gravity.CENTER);
        row.addView(icon, IrisUi.fixed(this, 30, 30));

        LinearLayout copy = IrisUi.vertical(this, 0);
        TextView preview = IrisUi.text(this, entry.preview, 12.5f, IrisUi.TEXT, Typeface.NORMAL);
        preview.setMaxLines(1);
        preview.setEllipsize(TextUtils.TruncateAt.END);
        copy.addView(preview, IrisUi.matchWrap());

        LinearLayout meta = IrisUi.horizontal(this, 0);
        String verdictLabel = TextUtils.isEmpty(entry.verdict) ? "Result" : entry.verdict;
        meta.addView(IrisUi.text(this, verdictLabel, 10.5f, color, Typeface.BOLD), IrisUi.rowWeight(1));
        TextView date = IrisUi.muted(this, checkedAt, 10.5f);
        date.setGravity(Gravity.END);
        meta.addView(date, IrisUi.rowWeight(1));
        copy.addView(meta, IrisUi.spaced(this, 3));

        LinearLayout.LayoutParams copyParams = IrisUi.rowWeight(1);
        copyParams.leftMargin = IrisUi.dp(this, 10);
        row.addView(copy, copyParams);

        row.setContentDescription(HistoryDetail.rowDescription(entry.verdict, entry.preview, checkedAt, false));
        row.setOnClickListener(view -> toggleDetail(entry, row, detail, checkedAt));

        cell.addView(row, IrisUi.matchWrap());
        cell.addView(detail, IrisUi.spaced(this, 8));
        return cell;
    }

    /**
     * Expands the stored check inside the panel instead of leaving for ResultActivity;
     * the full result stays one tap away from inside the detail. Tapping a second row
     * closes the first, so the list reads as one open verdict at a time, never a stack.
     */
    private void toggleDetail(HistoryStore.HistoryEntry entry, View row, LinearLayout detail, String checkedAt) {
        if (row.isSelected()) {
            openRecentDetail.close();
            return;
        }
        // Parse on first tap only: two rows a user never opens cost the panel nothing.
        if (detail.getChildCount() == 0) {
            detail.addView(
                HistoryDetail.build(this, entry, checkedAt, () -> openStoredResult(entry)),
                IrisUi.matchWrap()
            );
        }
        openRecentDetail.open(row, detail, entry, checkedAt);
    }

    /**
     * Re-runs the panel's existing height cap once the detail has settled, so extra
     * content scrolls inside the body instead of growing the overlay window past the
     * screen, and a collapse frees the fixed height that would otherwise leave an
     * empty strip below the shorter card. Width and drag behavior stay untouched.
     */
    private void repositionPanelForDetail() {
        if (panelParams != null) {
            panelParams.height = WindowManager.LayoutParams.WRAP_CONTENT;
        }
        positionPanelNearBubble(0);
        if (panel != null) panel.post(() -> positionPanelNearBubble(0));
    }

    /** Puts the panel away first, so the stored result opens over an idle bubble. */
    private void openStoredResult(HistoryStore.HistoryEntry entry) {
        resetToIdle();
        Intent launch = new Intent(this, ResultActivity.class);
        launch.putExtra(ResultActivity.EXTRA_RESPONSE_JSON, entry.rawJson);
        launch.putExtra(ResultActivity.EXTRA_FALLBACK_TEXT, entry.fallback);
        launch.putExtra(ResultActivity.EXTRA_INPUT_TYPE, entry.inputType);
        launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        startActivity(launch);
    }

    private void showScanningPanel(String type) {
        state = STATE_SCANNING;
        setBubbleActive(true);

        LinearLayout card = createPanelShell("SCANNING", view -> hidePanel());
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

        // Stopping the check is a decision, so it gets a button that says so. The X beside it
        // only puts the panel away, and the check carries on behind it.
        Button cancel = IrisUi.secondaryButton(this, "Cancel check");
        cancel.setOnClickListener(view -> cancelActiveScan());
        body.addView(cancel, IrisUi.spaced(this, 16));

        card.addView(body, IrisUi.matchWrap());
        showPanelView(card, false, panelHeightEstimate());
    }

    private View scanPreview(String value, boolean image) {
        LinearLayout box = IrisUi.vertical(this, 12);
        box.setBackground(IrisUi.bordered(this, IrisUi.BLUE_BG, 14, IrisUi.BLUE_OUTLINE));
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
        setBubbleReady(false);

        LinearLayout card = createPanelShell("VERIFICATION RESULT", view -> hidePanel());
        LinearLayout body = IrisUi.vertical(this, 16);

        if (resultData.claims.isEmpty()) {
            body.addView(ResultRenderer.errorCard(this, ResultRenderer.Variant.COMPACT,
                "IRIS did not return a readable result."), IrisUi.matchWrap());
        } else {
            body.addView(ResultRenderer.navigator(this, ResultRenderer.Variant.COMPACT, claimIndex,
                resultData.claims.size(),
                () -> {
                    claimIndex = Math.max(0, claimIndex - 1);
                    sourcesExpanded = false;
                    showResultPanel();
                },
                () -> {
                    if (resultData == null) return;
                    claimIndex = Math.min(resultData.claims.size() - 1, claimIndex + 1);
                    sourcesExpanded = false;
                    showResultPanel();
                }), IrisUi.matchWrap());
            body.addView(ResultRenderer.claimPanel(this, ResultRenderer.Variant.COMPACT,
                resultData.claims.get(claimIndex), "image".equals(currentInputType), sourcesExpanded,
                () -> {
                    sourcesExpanded = true;
                    showResultPanel();
                }), IrisUi.spaced(this, 12));
        }

        if (!resultData.skippedSegments.isEmpty()) {
            body.addView(ResultRenderer.skippedNote(this, resultData), IrisUi.spaced(this, 12));
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

        // Outside the scrolling area, so it is reachable without reading to the bottom first.
        // This is the one control that discards the result; the X only puts it away.
        LinearLayout footer = IrisUi.vertical(this, 0);
        Button done = IrisUi.secondaryButton(this, "Done");
        done.setOnClickListener(view -> resetToIdle());
        footer.addView(done, IrisUi.spaced(this, 12));
        card.addView(footer, IrisUi.matchWrap());

        showPanelView(card, false, resultPanelHeightEstimate());
    }

    private void showErrorPanel(String message) {
        state = STATE_ERROR;
        setBubbleActive(false);
        setBubbleReady(false);

        LinearLayout card = createPanelShell("CHECK FAILED", view -> hidePanel());
        LinearLayout body = IrisUi.vertical(this, 16);
        body.addView(ResultRenderer.errorCard(this, ResultRenderer.Variant.COMPACT,
            TextUtils.isEmpty(message) ? "IRIS could not complete the check." : message), IrisUi.matchWrap());

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
        // Every panel state is built through here, so this is where the theme must be
        // current: the panel is the overlay's own creation boundary.
        applyOverlayTheme();
        LinearLayout card = IrisUi.card(this, 0);
        card.setElevation(IrisUi.dp(this, 14));
        card.addView(panelHeader(modeLabel, closeListener), IrisUi.matchWrap());
        return card;
    }

    private View panelHeader(String label, View.OnClickListener closeListener) {
        LinearLayout header = IrisUi.horizontal(this, 12);
        // Radius tracks IrisUi.card so the gradient caps the panel instead of over-rounding it.
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
        anchorBubbleToUpperRight(() -> {
            if (panel != null && panel.getParent() != null) {
                positionPanelNearBubble();
            }
        });

        boolean attached = panel != null && panel.getParent() != null;
        if (!focusable) {
            hideKeyboard();
            claimInput = null;
            panelStatus = null;
        }
        if (attached) {
            // Keep the attached window across state changes, including the new input references.
            // The reused root keeps the fill it was first built with, so re-skin it: a theme
            // change must reach an open panel without rebuilding the overlay window.
            panel.setBackground(IrisUi.bordered(this, IrisUi.CARD, 18, IrisUi.BORDER));
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
                if (state == STATE_SCANNING || state == STATE_RESULT) {
                    hidePanel();
                } else {
                    resetToIdle();
                }
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
                if (state == STATE_SCANNING || state == STATE_RESULT) {
                    hidePanel();
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
        int screenWidth = getResources().getDisplayMetrics().widthPixels;
        int screenHeight = getResources().getDisplayMetrics().heightPixels;

        // Position panel right-aligned near the right edge, matching Messenger style
        int x = screenWidth - panelWidth - margin;
        if (x < margin) x = margin;

        Rect bounds = bubbleMovementBounds();
        // The bubble is anchored to the upper right; place panel directly below it
        int bubbleBottom = (isAnchoredToUpperRight ? bounds.top : bubbleParams.y) + bubbleParams.height;
        int y = bubbleBottom + IrisUi.dp(this, 8);

        panelParams.x = x;
        panelParams.y = y;
        panelParams.width = panelWidth;

        // Cap height so the panel never overflows the bottom of the screen or pushes up over the bubble
        int maxAvailableHeight = screenHeight - y - margin;
        if (maxAvailableHeight > 0) {
            int panelHeight = panel != null && panel.getHeight() > 0 ? panel.getHeight() : heightEstimate;
            if (panelHeight > maxAvailableHeight) {
                panelParams.height = maxAvailableHeight;
            } else {
                panelParams.height = WindowManager.LayoutParams.WRAP_CONTENT;
            }
        }

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
        return IrisUi.dp(this, 650);
    }

    private int resultBodyHeight() {
        int screenHeight = getResources().getDisplayMetrics().heightPixels;
        Rect bounds = bubbleMovementBounds();
        int bubbleBottom = (isAnchoredToUpperRight ? bounds.top : (bubbleParams != null ? bubbleParams.y : bounds.top))
            + (bubbleParams != null ? bubbleParams.height : IrisUi.dp(this, 68));
        int overhead = bubbleBottom + IrisUi.dp(this, 230);
        int available = screenHeight - overhead;
        return Math.max(IrisUi.dp(this, 260), Math.min(IrisUi.dp(this, 500), available));
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
            setPanelStatus("Clipboard does not contain readable text yet.", IrisUi.STATUS_ERROR);
            return;
        }

        String text = pasted.trim();
        claimInput.setText(text);
        claimInput.setSelection(claimInput.getText().length());
        setPanelStatus("Text pasted. Tap Check with IRIS when ready.", IrisUi.STATUS_OK);
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
            setPanelStatus("Paste or type claim text before checking.", IrisUi.STATUS_ERROR);
            return;
        }
        verifyTextSource(text);
    }

    private void openImagePicker() {
        removePanelView();
        returnBubbleToRestingPosition();
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
                deliverResult(responseJson);
            }

            @Override
            public void onError(String message) {
                if (token != requestToken) return;
                deliverError(message);
            }
        });
    }

    /**
     * Shows a finished result, or lets the bubble hold it until it is asked for.
     *
     * A panel that is not on screen was put away on purpose. Opening it the moment the check
     * finishes takes that decision back, over whatever the phone is doing by then.
     */
    private void deliverResult(String responseJson) {
        resultData = IrisResultData.parse(responseJson, currentFallbackText, currentInputType);
        claimIndex = 0;
        sourcesExpanded = false;
        pendingError = null;
        // Recorded before the panel decision so a put-away panel still lands in history;
        // HistoryStore never throws, so the delivery flow below is untouched.
        HistoryStore.record(this, responseJson, currentFallbackText, currentInputType);

        if (panel == null) {
            state = STATE_RESULT;
            setBubbleActive(false);
            setBubbleReady(true);
            return;
        }

        showResultPanel();
    }

    /** As deliverResult, for a check that failed. The message waits with the bubble. */
    private void deliverError(String message) {
        if (panel == null) {
            state = STATE_ERROR;
            pendingError = message;
            setBubbleActive(false);
            setBubbleReady(true);
            return;
        }

        showErrorPanel(message);
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
                deliverResult(responseJson);
            }

            @Override
            public void onError(String message) {
                if (token != requestToken) return;
                deliverError(message);
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

    private void setBubbleReady(boolean waiting) {
        if (bubble != null) bubble.setReady(waiting);
    }

    private void removePanelView() {
        if (state == STATE_INPUT) {
            exitPasteTextState();
        } else {
            hideKeyboard();
        }

        panelDismissedAt = SystemClock.uptimeMillis();

        if (windowManager != null && panel != null && panel.getParent() != null) {
            windowManager.removeView(panel);
        }
        panel = null;
        claimInput = null;
        panelStatus = null;
        panelParams = null;
        openRecentDetail.clear();
    }

    private void resetToIdle() {
        if (state == STATE_SCANNING) requestToken += 1;
        removePanelView();
        returnBubbleToRestingPosition();
        state = STATE_IDLE;
        claimIndex = 0;
        resultData = null;
        pendingError = null;
        currentFallbackText = "";
        currentInputType = "text";
        setBubbleActive(false);
        setBubbleReady(false);
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
