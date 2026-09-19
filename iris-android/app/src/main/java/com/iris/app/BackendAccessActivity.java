package com.iris.app;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.widget.TextView;

import java.net.InetAddress;
import java.net.URL;
import java.util.ArrayList;
import java.util.List;
import java.util.function.Consumer;

public class BackendAccessActivity extends Activity {
    private static final String PERMISSION = "android.permission.ACCESS_LOCAL_NETWORK";
    private static final int REQUEST_ACCESS = 4101;
    private static final List<PendingCheck> pendingChecks = new ArrayList<>();
    private boolean resolved;

    // Called on the network worker, because a configured hostname may need DNS resolution.
    static boolean needsPermission(Context context, URL url) throws Exception {
        if (Build.VERSION.SDK_INT < 37 || context.checkSelfPermission(PERMISSION) == PackageManager.PERMISSION_GRANTED) {
            return false;
        }
        for (InetAddress address : InetAddress.getAllByName(url.getHost())) {
            byte[] bytes = address.getAddress();
            boolean uniqueLocalV6 = bytes.length == 16 && (bytes[0] & 0xfe) == 0xfc;
            if (address.isSiteLocalAddress() || address.isLinkLocalAddress() || uniqueLocalV6) return true;
        }
        return false;
    }

    // All queue access happens on the main thread. Checks resume only after explicit consent.
    static void requestAccess(Context context, Runnable retry, Consumer<String> fail) {
        boolean alreadyRequesting = !pendingChecks.isEmpty();
        pendingChecks.add(new PendingCheck(retry, fail));
        if (alreadyRequesting) return;
        try {
            Intent intent = new Intent(context, BackendAccessActivity.class);
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            context.startActivity(intent);
        } catch (Exception error) {
            completePending(false);
        }
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (pendingChecks.isEmpty()) {
            resolved = true;
            finish();
            return;
        }
        TextView explanation = IrisUi.text(this,
            "IRIS needs Nearby devices permission to connect to the verification server on your computer.",
            18, IrisUi.TEXT, android.graphics.Typeface.NORMAL);
        int padding = IrisUi.dp(this, 28);
        explanation.setPadding(padding, padding * 2, padding, padding);
        setContentView(explanation);

        if (Build.VERSION.SDK_INT < 37 || checkSelfPermission(PERMISSION) == PackageManager.PERMISSION_GRANTED) {
            resolve(true);
        } else if (savedInstanceState == null) {
            requestPermissions(new String[] { PERMISSION }, REQUEST_ACCESS);
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQUEST_ACCESS) {
            resolve(grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED);
        }
    }

    private void resolve(boolean granted) {
        resolved = true;
        finish();
        completePending(granted);
    }

    private static void completePending(boolean granted) {
        List<PendingCheck> checks = new ArrayList<>(pendingChecks);
        pendingChecks.clear();
        for (PendingCheck check : checks) {
            if (granted) check.retry.run();
            else check.fail.accept("Local network access is not allowed. Enable Nearby devices for IRIS in Android Settings > Apps > IRIS > Permissions, then retry.");
        }
    }

    @Override
    protected void onDestroy() {
        if (isFinishing() && !resolved) completePending(false);
        super.onDestroy();
    }

    private static final class PendingCheck {
        final Runnable retry;
        final Consumer<String> fail;

        PendingCheck(Runnable retry, Consumer<String> fail) {
            this.retry = retry;
            this.fail = fail;
        }
    }
}
