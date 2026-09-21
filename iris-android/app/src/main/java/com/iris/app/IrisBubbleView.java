package com.iris.app;

import android.animation.ValueAnimator;
import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.Shader;
import android.view.animation.LinearInterpolator;
import android.widget.FrameLayout;

public class IrisBubbleView extends FrameLayout {
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private boolean active;
    // Something finished while the panel was put away. The bubble says so quietly and waits
    // to be asked, rather than taking the screen back on its own.
    private boolean ready;
    private float pulse;
    private ValueAnimator animator;

    public IrisBubbleView(Context context) {
        super(context);
        setWillNotDraw(false);
        setClipChildren(false);
        setClipToPadding(false);
        setClickable(true);
        setContentDescription("Open IRIS panel");
        IrisUi.touchFeedback(this, 999);
        IrisMotion.observe(this, this::updateMotion);
    }

    public void setActive(boolean value) {
        if (active == value) return;

        active = value;
        // A new check replaces whatever was waiting to be read.
        if (active) ready = false;
        describe();
        updateMotion();
    }

    public void setReady(boolean value) {
        if (ready == value) return;

        ready = value;
        describe();
        invalidate();
    }

    private void describe() {
        if (active) {
            setContentDescription("IRIS is scanning. Open panel");
        } else if (ready) {
            setContentDescription("IRIS has a result ready. Open panel");
        } else {
            setContentDescription("Open IRIS panel");
        }
    }

    private void updateMotion() {
        if (active && isAttachedToWindow() && isShown() && IrisMotion.animationsEnabled()) startPulse();
        else stopPulse();
        invalidate();
    }

    @Override
    protected void onWindowVisibilityChanged(int visibility) {
        super.onWindowVisibilityChanged(visibility);
        updateMotion();
    }

    @Override
    protected void onDetachedFromWindow() {
        stopPulse();
        super.onDetachedFromWindow();
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);

        float centerX = getWidth() / 2f;
        float centerY = getHeight() / 2f;
        float radius = Math.min(getWidth(), getHeight()) / 2f - IrisUi.dp(getContext(), 8);

        if (active) {
            float pulseRadius = radius + IrisUi.dp(getContext(), 7) * pulse;
            paint.setStyle(Paint.Style.FILL);
            paint.setShader(null);
            paint.setColor(Color.argb(Math.round(48 * (1f - pulse)), 139, 92, 246));
            canvas.drawCircle(centerX, centerY, pulseRadius, paint);

            paint.setShader(new LinearGradient(
                centerX - radius,
                centerY + radius,
                centerX + radius,
                centerY - radius,
                new int[] { IrisUi.GRADIENT_START, IrisUi.GRADIENT_MID, IrisUi.GRADIENT_END },
                new float[] { 0f, 0.55f, 1f },
                Shader.TileMode.CLAMP
            ));
            canvas.drawCircle(centerX, centerY, radius, paint);
            paint.setShader(null);
            return;
        }

        paint.setStyle(Paint.Style.FILL);
        paint.setColor(Color.WHITE);
        canvas.drawCircle(centerX, centerY, radius, paint);

        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeWidth(IrisUi.dp(getContext(), 2));
        paint.setColor(IrisUi.GRADIENT_END);
        canvas.drawCircle(centerX, centerY, radius - IrisUi.dp(getContext(), 1), paint);

        if (!ready) return;

        // A dot on the shoulder of the bubble, ringed in white so it reads against whatever
        // is behind it. GRADIENT_END is too pale here; the mid violet carries.
        float badge = IrisUi.dp(getContext(), 7);
        float badgeX = centerX + radius * 0.7f;
        float badgeY = centerY - radius * 0.7f;

        paint.setStyle(Paint.Style.FILL);
        paint.setColor(Color.WHITE);
        canvas.drawCircle(badgeX, badgeY, badge + IrisUi.dp(getContext(), 2), paint);
        paint.setColor(IrisUi.GRADIENT_MID);
        canvas.drawCircle(badgeX, badgeY, badge, paint);
    }

    private void startPulse() {
        if (animator != null) return;

        animator = ValueAnimator.ofFloat(0f, 1f);
        animator.setDuration(1150);
        animator.setRepeatCount(ValueAnimator.INFINITE);
        animator.setInterpolator(new LinearInterpolator());
        animator.addUpdateListener(animation -> {
            pulse = (float) animation.getAnimatedValue();
            invalidate();
        });
        animator.start();
    }

    private void stopPulse() {
        if (animator != null) {
            animator.cancel();
            animator = null;
        }
        pulse = 0f;
    }
}
