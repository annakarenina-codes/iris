package com.iris.app;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Shader;
import android.view.View;

public class IrisToggleView extends View {
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG | Paint.DITHER_FLAG);
    private boolean checked;
    private Bitmap logo;

    public IrisToggleView(Context context) {
        super(context);
        setClickable(true);
        IrisUi.touchFeedback(this, 999);
    }

    public void setChecked(boolean value) {
        checked = value;
        invalidate();
    }

    public boolean isChecked() {
        return checked;
    }

    @Override
    protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {
        int width = IrisUi.dp(getContext(), 64);
        int height = IrisUi.dp(getContext(), 34);
        setMeasuredDimension(resolveSize(width, widthMeasureSpec), resolveSize(height, heightMeasureSpec));
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);

        float width = getWidth();
        float height = getHeight();
        RectF track = new RectF(0, 0, width, height);

        paint.setStyle(Paint.Style.FILL);
        if (checked) {
            paint.setShader(new LinearGradient(
                0,
                height,
                width,
                0,
                new int[] { IrisUi.GRADIENT_START, IrisUi.GRADIENT_MID, IrisUi.GRADIENT_END },
                new float[] { 0f, 0.55f, 1f },
                Shader.TileMode.CLAMP
            ));
        } else {
            paint.setShader(null);
            paint.setColor(Color.rgb(229, 231, 235));
        }
        canvas.drawRoundRect(track, height / 2f, height / 2f, paint);
        paint.setShader(null);

        float knobRadius = height / 2f - IrisUi.dp(getContext(), 3);
        float knobCenterX = checked ? width - height / 2f : height / 2f;
        float knobCenterY = height / 2f;

        paint.setColor(Color.WHITE);
        canvas.drawCircle(knobCenterX, knobCenterY, knobRadius, paint);

        if (checked) {
            drawLogo(canvas, knobCenterX, knobCenterY, knobRadius * 1.35f);
        } else {
            paint.setColor(Color.rgb(107, 114, 128));
            paint.setTextAlign(Paint.Align.CENTER);
            paint.setTextSize(IrisUi.dp(getContext(), 10));
            paint.setFakeBoldText(true);
            Paint.FontMetrics metrics = paint.getFontMetrics();
            float baseline = knobCenterY - (metrics.ascent + metrics.descent) / 2f;
            canvas.drawText("OFF", knobCenterX, baseline, paint);
            paint.setFakeBoldText(false);
        }
    }

    private void drawLogo(Canvas canvas, float centerX, float centerY, float size) {
        Bitmap mark = getLogo();
        if (mark == null) return;

        float left = centerX - size / 2f;
        float top = centerY - size / 2f;
        canvas.drawBitmap(mark, null, new RectF(left, top, left + size, top + size), paint);
    }

    private Bitmap getLogo() {
        if (logo == null) {
            logo = BitmapFactory.decodeResource(getResources(), R.drawable.iris_logo_mark);
        }
        return logo;
    }
}
