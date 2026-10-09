package com.example.scamshield_mobile

import android.app.Activity
import android.content.Intent
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.File
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import org.json.JSONObject

class MainActivity : FlutterActivity() {
    private val requestCode = 3003
    private val executor = Executors.newSingleThreadExecutor()
    private var pending: MethodChannel.Result? = null
    private var source: File? = null
    private var cancelled = AtomicBoolean(false)
    private var pickerOpen = false
    private var maximumBytes = 0L
    private var expiresAt = 0L
    private var owner = ""

    private fun available(file: File, expectedOwner: String, expiry: Long, limit: Long): Boolean = try {
        val root = File(cacheDir, "scamshield-private").canonicalFile
        val metadata = JSONObject(File(file.path + ".meta").readText())
        file.isFile && file.canonicalPath.startsWith(root.path + File.separator) &&
            file.name.endsWith(".jsonl") && file.length() <= limit && limit > 0 &&
            metadata.getString("owner") == expectedOwner && metadata.getLong("expires_at") == expiry &&
            expiry > System.currentTimeMillis()
    } catch (_: Exception) { false }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "scamshield/privacy").setMethodCallHandler { call, result ->
            when (call.method) {
                "cancelExport" -> {
                    cancelled.set(true)
                    pending?.success(false)
                    pending = null
                    source = null
                    result.success(null)
                }
                "saveExport" -> {
                    val path = call.argument<String>("path")
                    val file = path?.let { File(it).canonicalFile }
                    val root = File(cacheDir, "scamshield-private").canonicalFile
                    val limit = call.argument<Number>("maxBytes")?.toLong()
                    val expiry = call.argument<Number>("expiresAt")?.toLong()
                    val expectedOwner = call.argument<String>("owner")
                    if (pickerOpen || pending != null || file == null || !file.isFile || limit == null || limit <= 0 ||
                        !file.path.startsWith(root.path + File.separator) || expiry == null || expectedOwner == null ||
                        !available(file, expectedOwner, expiry, limit)) {
                        result.error("unavailable", "Export unavailable", null)
                    } else {
                        source = file
                        pending = result
                        maximumBytes = limit
                        expiresAt = expiry
                        owner = expectedOwner
                        pickerOpen = true
                        cancelled = AtomicBoolean(false)
                        val intent = Intent(Intent.ACTION_CREATE_DOCUMENT).apply {
                            addCategory(Intent.CATEGORY_OPENABLE)
                            type = "application/x-ndjson"
                            putExtra(Intent.EXTRA_TITLE, "scamshield-export.jsonl")
                        }
                        startActivityForResult(intent, requestCode)
                    }
                }
                else -> result.notImplemented()
            }
        }
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != this.requestCode) return
        pickerOpen = false
        val callback = pending ?: return
        val file = source
        val uri = data?.data
        val cancellation = cancelled
        val limit = maximumBytes
        val expiry = expiresAt
        val expectedOwner = owner
        if (resultCode != Activity.RESULT_OK || uri == null || file == null) {
            pending = null
            source = null
            callback.success(false)
            return
        }
        executor.execute {
            var success = false
            try {
                if (cancellation.get() || !available(file, expectedOwner, expiry, limit)) throw IllegalStateException("unavailable")
                file.inputStream().use { input ->
                    if (cancellation.get() || !available(file, expectedOwner, expiry, limit)) throw IllegalStateException("unavailable")
                    contentResolver.openOutputStream(uri, "w")!!.use { output ->
                        val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
                        var total = 0L
                        while (true) {
                            if (cancellation.get() || !available(file, expectedOwner, expiry, limit)) throw IllegalStateException("unavailable")
                            val size = input.read(buffer)
                            if (size < 0) break
                            total += size
                            if (total > limit) throw IllegalStateException("size")
                            if (cancellation.get() || !available(file, expectedOwner, expiry, limit)) throw IllegalStateException("unavailable")
                            output.write(buffer, 0, size)
                        }
                    }
                }
                success = !cancellation.get() && available(file, expectedOwner, expiry, limit)
            } catch (_: Exception) { success = false }
            if (!success) {
                try { contentResolver.delete(uri, null, null) } catch (_: Exception) { }
            }
            runOnUiThread {
                if (pending === callback) {
                    pending = null
                    source = null
                    callback.success(success)
                }
            }
        }
    }

    override fun onDestroy() {
        cancelled.set(true)
        executor.shutdown()
        super.onDestroy()
    }
}
