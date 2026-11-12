package com.istishraf.app;

import android.os.Bundle;
import android.webkit.WebView;
import androidx.activity.OnBackPressedCallback;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                WebView webView = getBridge() != null ? getBridge().getWebView() : null;
                if (webView == null) {
                    exitApp();
                    return;
                }

                webView.evaluateJavascript(
                    "(function(){ return window.__istishrafHandleBack ? window.__istishrafHandleBack() : 'fallback'; })()",
                    result -> {
                        if (result != null && result.contains("handled")) {
                            return;
                        }
                        if (result != null && result.contains("exit")) {
                            exitApp();
                            return;
                        }
                        String currentUrl = webView.getUrl();
                        boolean isHome = currentUrl != null && (
                            currentUrl.endsWith(".app/") ||
                            currentUrl.endsWith(".app") ||
                            currentUrl.endsWith("localhost/") ||
                            currentUrl.endsWith("localhost")
                        );
                        if (!isHome && webView.canGoBack()) {
                            webView.goBack();
                        } else if (!isHome) {
                            webView.loadUrl("https://istishraf-future.vercel.app/");
                        } else {
                            exitApp();
                        }
                    }
                );
            }

            private void exitApp() {
                setEnabled(false);
                MainActivity.this.getOnBackPressedDispatcher().onBackPressed();
                setEnabled(true);
            }
        });
    }
}
