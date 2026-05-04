package com.terminalface

import android.view.SurfaceHolder
import androidx.wear.watchface.*
import androidx.wear.watchface.style.CurrentUserStyleRepository

class TerminalWatchFaceService : WatchFaceService() {

    // Context is not available at construction time; pass it lazily via applicationContext
    override fun createUserStyleSchema() =
        TerminalStyleSchema.createUserStyleSchema()

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
        // WatchFace.LegacyWatchFaceStyle does not exist in watchface 1.2.x
        return WatchFace(WatchFaceType.DIGITAL, renderer)
    }
}
