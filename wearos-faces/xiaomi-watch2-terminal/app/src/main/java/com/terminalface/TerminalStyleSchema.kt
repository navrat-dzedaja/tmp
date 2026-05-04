package com.terminalface

import androidx.wear.watchface.style.UserStyleSchema
import androidx.wear.watchface.style.UserStyleSetting
import androidx.wear.watchface.style.WatchFaceLayer

object TerminalStyleSchema {

    // UserStyleSetting.ListUserStyleSetting.Id does not exist in watchface 1.2.x —
    // use the base UserStyleSetting.Id instead.
    val COLOR_STYLE_SETTING = UserStyleSetting.Id("color_style")

    fun createUserStyleSchema(): UserStyleSchema {
        val colorOptions = TerminalTheme.NAMES.map { name ->
            UserStyleSetting.ListUserStyleSetting.ListOption(
                id              = UserStyleSetting.Option.Id(name),
                displayName     = name,
                screenReaderName = name,
                icon            = null,
            )
        }

        val colorSetting = UserStyleSetting.ListUserStyleSetting(
            id          = UserStyleSetting.Id("color_style"),
            displayName = "Colour Theme",
            description = "Terminal colour theme",
            icon        = null,
            options     = colorOptions,
            affectsWatchFaceLayers = listOf(
                WatchFaceLayer.BASE,
                WatchFaceLayer.COMPLICATIONS,
            ),
        )

        return UserStyleSchema(listOf(colorSetting))
    }
}
