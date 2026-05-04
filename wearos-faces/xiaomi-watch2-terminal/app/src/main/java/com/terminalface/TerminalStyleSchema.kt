package com.terminalface

import android.content.Context
import androidx.wear.watchface.style.UserStyleSchema
import androidx.wear.watchface.style.UserStyleSetting
import androidx.wear.watchface.style.WatchFaceLayer

/** User-selectable style options exposed in the watch face picker. */
object TerminalStyleSchema {

    val COLOR_STYLE_SETTING = UserStyleSetting.ListUserStyleSetting.Id("color_style")

    fun createUserStyleSchema(context: Context): UserStyleSchema {
        val colorOptions = TerminalTheme.NAMES.map { name ->
            UserStyleSetting.ListUserStyleSetting.ListOption(
                id          = UserStyleSetting.Option.Id(name),
                resources   = context.resources,
                displayNameResourceId = R.string.watch_face_name,   // reuse label
                screenReaderNameResourceId = R.string.watch_face_name,
                icon        = null,
            )
        }

        val colorSetting = UserStyleSetting.ListUserStyleSetting(
            id                   = COLOR_STYLE_SETTING,
            resources            = context.resources,
            displayNameResourceId = R.string.watch_face_config,
            descriptionResourceId = R.string.watch_face_config,
            icon                 = null,
            options              = colorOptions,
            affectsWatchFaceLayers = listOf(
                WatchFaceLayer.BASE,
                WatchFaceLayer.COMPLICATIONS,
            ),
        )

        return UserStyleSchema(listOf(colorSetting))
    }
}
