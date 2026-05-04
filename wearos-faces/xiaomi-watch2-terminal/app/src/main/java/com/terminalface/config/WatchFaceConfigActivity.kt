package com.terminalface.config

import android.app.Activity
import android.os.Bundle
import android.widget.LinearLayout
import android.widget.RadioButton
import android.widget.RadioGroup
import android.widget.ScrollView
import android.widget.TextView
import androidx.wear.watchface.editor.EditorSession
import com.terminalface.TerminalStyleSchema
import com.terminalface.TerminalTheme
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Simple configuration activity — lets the user pick a colour theme.
 * In a full implementation you would also let them configure each
 * complication slot via [EditorSession.openComplicationDataSourceChooser].
 */
class WatchFaceConfigActivity : Activity() {

    private lateinit var editorSession: EditorSession
    private val scope = CoroutineScope(Dispatchers.Main)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        scope.launch {
            editorSession = EditorSession.createOnWatchEditorSession(this@WatchFaceConfigActivity)
            buildUi()
        }
    }

    private fun buildUi() {
        val root = ScrollView(this)
        val col  = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }

        val header = TextView(this).apply {
            text     = "TERMINAL WATCH FACE\nColour Theme"
            setPadding(24, 24, 24, 12)
        }
        col.addView(header)

        val radioGroup = RadioGroup(this)
        TerminalTheme.NAMES.forEachIndexed { index, name ->
            val rb = RadioButton(this).apply {
                text = name
                id   = index
            }
            radioGroup.addView(rb)
        }
        col.addView(radioGroup)

        radioGroup.setOnCheckedChangeListener { _, checkedId ->
            scope.launch {
                val session = editorSession
                val currentStyle = session.userStyle.value.toMutableUserStyle()
                val setting = session.userStyleSchema.userStyleSettings
                    .first { it.id == TerminalStyleSchema.COLOR_STYLE_SETTING }
                    as androidx.wear.watchface.style.UserStyleSetting.ListUserStyleSetting
                currentStyle[setting] = setting.options[checkedId]
                    as androidx.wear.watchface.style.UserStyleSetting.ListUserStyleSetting.ListOption
                session.userStyle.value = currentStyle.toUserStyle()
            }
        }

        root.addView(col)
        setContentView(root)
    }

    override fun onDestroy() {
        super.onDestroy()
        editorSession.close()
    }
}
