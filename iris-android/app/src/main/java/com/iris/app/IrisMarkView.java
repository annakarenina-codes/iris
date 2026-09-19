package com.iris.app;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.view.View;

public class IrisMarkView extends View {
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG | Paint.DITHER_FLAG);
    private Bitmap logo;

    public IrisMarkView(Context context) {
        super(context);
    }

    public void setMonochrome(boolean value) {
        invalidate();
    }

    @Override
    protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {
        int desired = IrisUi.dp(getContext(), 34);
        int width = resolveSize(desired, widthMeasureSpec);
        int height = resolveSize(desired, heightMeasureSpec);
        int size = Math.min(width, height);
        setMeasuredDimension(size, size);
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);

        Bitmap mark = getLogo();
        if (mark == null || mark.getWidth() <= 0 || mark.getHeight() <= 0) {
            return;
        }

        float viewWidth = getWidth();
        float viewHeight = getHeight();
        float scale = Math.min(viewWidth / mark.getWidth(), viewHeight / mark.getHeight());
        float drawWidth = mark.getWidth() * scale;
        float drawHeight = mark.getHeight() * scale;
        float left = (viewWidth - drawWidth) / 2f;
        float top = (viewHeight - drawHeight) / 2f;

        RectF destination = new RectF(left, top, left + drawWidth, top + drawHeight);
        canvas.drawBitmap(mark, null, destination, paint);
    }

    private Bitmap getLogo() {
        if (logo == null) {
            logo = BitmapFactory.decodeResource(getResources(), R.drawable.iris_logo_mark);
        }
        return logo;
    }
}
