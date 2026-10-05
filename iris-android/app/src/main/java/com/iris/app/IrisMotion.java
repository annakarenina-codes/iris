package com.iris.app;

import android.animation.Animator;
import android.animation.AnimatorListenerAdapter;
import android.animation.ValueAnimator;
import android.database.ContentObserver;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.view.View;
import android.view.ViewGroup;
import android.view.animation.DecelerateInterpolator;

final class IrisMotion {
    private IrisMotion() {}

    static boolean animationsEnabled() {
        return ValueAnimator.areAnimatorsEnabled();
    }

    /**
     * Folds a panel section open or shut, animating its height and alpha together so
     * the overlay window grows into place instead of snapping between two layouts.
     *
     * Motion decides the transition, never the result: with animators disabled the
     * section swaps instantly exactly as it did before, and `onSettled` still fires, so
     * the caller's window reposition never waits on motion the user turned off.
     *
     * `onSettled` also fires once the fold lands, which is the point -- the panel only
     * re-derives its height cap after the height is final, or it re-caps against a
     * mid-animation measurement.
     */
    static void fold(ViewGroup content, boolean expanded, Runnable onSettled) {
        ViewGroup.LayoutParams params = content.getLayoutParams();
        if (params == null) {
            content.setVisibility(expanded ? View.VISIBLE : View.GONE);
            onSettled.run();
            return;
        }

        cancelFold(content);

        int start;
        int target;
        if (expanded) {
            // A folded section has no height to grow from, so measure it at the parent's
            // laid-out width first. Tapping is only possible once the panel has laid out,
            // so that width is real by now.
            View parent = (View) content.getParent();
            int width = parent != null && parent.getWidth() > 0 ? parent.getWidth() : content.getWidth();
            // forceLayout clears any cached height from when the section was last open,
            // so an unchanged MeasureSpec cannot hand back a stale target.
            content.forceLayout();
            content.measure(
                View.MeasureSpec.makeMeasureSpec(width, View.MeasureSpec.EXACTLY),
                View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED));
            start = 0;
            target = content.getMeasuredHeight();
        } else {
            // Stays visible until the fold lands; GONE mid-collapse would pop it out.
            start = content.getHeight();
            target = 0;
        }

        // Nothing to animate is a result, not a motion problem: land it without one
        // rather than counting a zero-distance animator through its full duration.
        if (!animationsEnabled() || start == target) {
            params.height = ViewGroup.LayoutParams.WRAP_CONTENT;
            content.setAlpha(1f);
            content.setVisibility(expanded ? View.VISIBLE : View.GONE);
            content.requestLayout();
            onSettled.run();
            return;
        }

        content.setVisibility(View.VISIBLE);
        params.height = start;
        content.setAlpha(expanded ? 0f : 1f);
        content.requestLayout();

        ValueAnimator animator = ValueAnimator.ofInt(start, target);
        animator.setDuration(expanded ? 200 : 160);
        animator.setInterpolator(new DecelerateInterpolator());
        // A re-tap cancels the running fold. Cancellation also reaches onAnimationEnd,
        // so the losing animator must not restore visibility or re-enter the caller.
        boolean[] cancelled = { false };
        animator.addUpdateListener(update -> {
            params.height = (int) update.getAnimatedValue();
            float fraction = update.getAnimatedFraction();
            content.setAlpha(expanded ? fraction : 1f - fraction);
            content.requestLayout();
        });
        animator.addListener(new AnimatorListenerAdapter() {
            @Override
            public void onAnimationCancel(Animator animation) {
                cancelled[0] = true;
            }

            @Override
            public void onAnimationEnd(Animator animation) {
                if (cancelled[0]) return;
                content.setTag(null);
                params.height = ViewGroup.LayoutParams.WRAP_CONTENT;
                content.setAlpha(1f);
                content.setVisibility(expanded ? View.VISIBLE : View.GONE);
                content.requestLayout();
                onSettled.run();
            }
        });
        content.setTag(animator);
        animator.start();
    }

    /** Drops any fold already running on this section, so a re-tap starts from where it is. */
    private static void cancelFold(ViewGroup content) {
        Object running = content.getTag();
        if (running instanceof ValueAnimator) {
            ((ValueAnimator) running).cancel();
        }
        content.setTag(null);
    }

    // Follow changes while visible, including when an overlay survives a trip to Settings.
    static void observe(View view, Runnable update) {
        ContentObserver observer = new ContentObserver(new Handler(Looper.getMainLooper())) {
            @Override
            public void onChange(boolean selfChange) {
                update.run();
            }
        };
        view.addOnAttachStateChangeListener(new View.OnAttachStateChangeListener() {
            @Override
            public void onViewAttachedToWindow(View attached) {
                attached.getContext().getContentResolver().registerContentObserver(
                    Settings.Global.getUriFor(Settings.Global.ANIMATOR_DURATION_SCALE), false, observer
                );
                update.run();
            }

            @Override
            public void onViewDetachedFromWindow(View detached) {
                detached.getContext().getContentResolver().unregisterContentObserver(observer);
            }
        });
    }
}
