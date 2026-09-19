package com.iris.app;

import android.animation.ValueAnimator;
import android.database.ContentObserver;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.view.View;

final class IrisMotion {
    private IrisMotion() {}

    static boolean animationsEnabled() {
        return ValueAnimator.areAnimatorsEnabled();
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
