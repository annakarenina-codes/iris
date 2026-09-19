package com.iris.app;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;

public class PickImageActivity extends Activity {
    private static final int PICK_IMAGE_REQUEST = 6101;
    private boolean pickerOpened;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (savedInstanceState != null) {
            pickerOpened = savedInstanceState.getBoolean("picker_opened", false);
        }
        if (!pickerOpened) {
            openImagePicker();
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        outState.putBoolean("picker_opened", pickerOpened);
        super.onSaveInstanceState(outState);
    }

    private void openImagePicker() {
        pickerOpened = true;
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("image/*");
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
        startActivityForResult(intent, PICK_IMAGE_REQUEST);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != PICK_IMAGE_REQUEST || resultCode != RESULT_OK || data == null) {
            finish();
            return;
        }

        Uri imageUri = data.getData();
        if (imageUri == null) {
            finish();
            return;
        }

        int flags = data.getFlags() & (Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
        if ((flags & Intent.FLAG_GRANT_READ_URI_PERMISSION) != 0) {
            try {
                getContentResolver().takePersistableUriPermission(imageUri, Intent.FLAG_GRANT_READ_URI_PERMISSION);
            } catch (Exception ignored) {
            }
        }

        grantUriPermission(getPackageName(), imageUri, Intent.FLAG_GRANT_READ_URI_PERMISSION);
        Intent service = new Intent(this, OverlayService.class);
        service.setAction(OverlayService.ACTION_VERIFY_IMAGE_URI);
        service.putExtra(OverlayService.EXTRA_IMAGE_URI, imageUri.toString());
        service.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        startOverlayService(service);
        finish();
    }

    private void startOverlayService(Intent intent) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent);
        } else {
            startService(intent);
        }
    }
}
