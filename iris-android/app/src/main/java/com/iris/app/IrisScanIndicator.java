package com.iris.app;

import android.content.Context;
import android.view.Gravity;
import android.widget.FrameLayout;
import android.widget.ProgressBar;

final class IrisScanIndicator extends FrameLayout {
    private final ProgressBar spinner;
    private final IrisMarkView staticMark;

    IrisScanIndicator(Context context) {
        super(context);
        spinner = new ProgressBar(context);
        spinner.setIndeterminate(true);
        staticMark = new IrisMarkView(context);
        int size = IrisUi.dp(context, 48);
        addView(spinner, new LayoutParams(size, size, Gravity.CENTER));
        addView(staticMark, new LayoutParams(size, size, Gravity.CENTER));
        setContentDescription("Verification in progress");
        IrisMotion.observe(this, this::updateMotion);
        updateMotion();
    }

    private void updateMotion() {
        boolean animate = IrisMotion.animationsEnabled();
        spinner.setVisibility(animate ? VISIBLE : GONE);
        staticMark.setVisibility(animate ? GONE : VISIBLE);
    }
}
