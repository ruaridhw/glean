package com.ruaridhw.glean

import android.util.Log
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    // Dart's GleanLogger sends every line here so it reaches logcat under the stable `glean` tag
    // (`adb logcat -s glean`); Flutter's own print/developer.log would use the `flutter` tag or nothing.
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "glean/log")
            .setMethodCallHandler { call, result ->
                if (call.method != "log") {
                    result.notImplemented()
                    return@setMethodCallHandler
                }
                val tag = call.argument<String>("tag") ?: "glean"
                val message = call.argument<String>("message") ?: ""
                when (call.argument<String>("level")) {
                    "error" -> Log.e(tag, message)
                    "warning" -> Log.w(tag, message)
                    else -> Log.i(tag, message)
                }
                result.success(null)
            }
    }
}
