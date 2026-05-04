package com.terminalface

import android.view.SurfaceHolder
import androidx.wear.watchface.*
import androidx.wear.watchface.style.CurrentUserStyleRepository

/**
 * Entry point for the watch face.  Android OS binds to this service via the
 * BIND_WALLPAPER permission and starts rendering through [TerminalRenderer].
 */
class TerminalWatchFaceService : WatchFaceService() {

    override fun createUserStyleSchema() =
        TerminalStyleSchema.createUserStyleSchema(applicationContext)

    override fun createComplicationSlotsManager(
        currentUserStyleRepository: CurrentUserStyleRepository,
    ) = ComplicationConfig.createComplicationSlotsManager(
        context = applicationContext,
        currentUserStyleRepository = currentUserStyleRepository,
    )

    override suspend fun createWatchFace(
        surfaceHolder: SurfaceHolder,
        watchState: WatchState,
        complicationSlotsManager: ComplicationSlotsManager,
        currentUserStyleRepository: CurrentUserStyleRepository,
    ): WatchFace {
        val renderer = TerminalRenderer(
            context                    = applicationContext,
            surfaceHolder              = surfaceHolder,
            currentUserStyleRepository = currentUserStyleRepository,
            watchState                 = watchState,
            complicationSlotsManager   = complicationSlotsManager,
            canvasType                 = CanvasType.HARDWARE,
        )
        return WatchFace(WatchFaceType.DIGITAL, renderer)
            .setLegacyWatchFaceStyle(
                WatchFace.LegacyWatchFaceStyle(
                    viewProtectionMode              = 0,
                    statusBarGravity                = 0,
                    tapEventsAccepted               = true,
                    accentColor                     = android.graphics.Color.parseColor("#00FF41"),
                )
            )
    }
}
