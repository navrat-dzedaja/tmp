package com.terminalface.config

import android.app.Activity
import android.os.Bundle
import android.widget.TextView

/**
 * Stub config activity required by the manifest.
 *
 * Full complication and theme configuration is done directly on the watch:
 *   long-press watch face → Edit → tap any slot or the style picker.
 *
 * To add a proper in-app editor, add the `watchface-editor` artifact and
 * implement EditorSession.createOnWatchEditorSession().
 */
class WatchFaceConfigActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(TextView(this).apply {
            text = "Configure complications and colour theme by long-pressing the watch face on the watch."
            setPadding(32, 48, 32, 48)
        })
    }
}
