package com.terminalface

import android.content.Context
import android.graphics.RectF
import androidx.wear.watchface.CanvasComplicationFactory
import androidx.wear.watchface.ComplicationSlot
import androidx.wear.watchface.ComplicationSlotsManager
import androidx.wear.watchface.complications.ComplicationSlotBounds
import androidx.wear.watchface.complications.DefaultComplicationDataSourcePolicy
import androidx.wear.watchface.complications.SystemDataSources
import androidx.wear.watchface.complications.data.ComplicationType
import androidx.wear.watchface.complications.rendering.CanvasComplicationDrawable
import androidx.wear.watchface.complications.rendering.ComplicationDrawable
import androidx.wear.watchface.style.CurrentUserStyleRepository

/**
 * 14 complication slots arranged in a terminal-grid layout on a 466×466 round display.
 *
 * Slot IDs are stable — changing them breaks existing user configurations.
 *
 * Visual layout (normalised 0..1 coords, centred on round screen):
 *
 *   ┌─────────────────────────────────┐
 *   │  [01 BATT]          [02 NOTIF]  │
 *   │─────────── HH:MM:SS ────────────│
 *   │─────────── DAY DATE ────────────│
 *   │  [03 HR  ]          [04 TEMP ]  │
 *   │  [05 SPO2]          [06 WTHR ]  │
 *   │  [07 STEP]          [08 CAL  ]  │
 *   │  [09 DIST]          [10 UV   ]  │
 *   │  [11 SLEP]          [12 STRS ]  │
 *   │  [13 ALM ]  [14 TZ2] [15SUNRS]  │
 *   │           [16 FLOOR]            │
 *   └─────────────────────────────────┘
 *
 * Bounds are in the 0..1 normalised space of the square bounding box.
 */
object ComplicationConfig {

    // ── Stable slot IDs ────────────────────────────────────────────────────
    const val BATTERY        = 1
    const val NOTIFICATIONS  = 2
    const val HEART_RATE     = 3
    const val TEMPERATURE    = 4
    const val SPO2           = 5
    const val WEATHER        = 6
    const val STEPS          = 7
    const val CALORIES       = 8
    const val DISTANCE       = 9
    const val UV_INDEX       = 10
    const val SLEEP          = 11
    const val STRESS         = 12
    const val ALARM          = 13
    const val WORLD_CLOCK    = 14
    const val SUNRISE        = 15
    const val FLOORS         = 16

    // ── Supported types per slot ───────────────────────────────────────────
    private val SHORT_TEXT_TYPES = listOf(
        ComplicationType.SHORT_TEXT,
        ComplicationType.RANGED_VALUE,
        ComplicationType.SMALL_IMAGE,
    )
    private val LONG_TEXT_TYPES = listOf(
        ComplicationType.LONG_TEXT,
        ComplicationType.SHORT_TEXT,
    )

    // ── Complication bounds (normalised) ───────────────────────────────────
    // Each RectF(left, top, right, bottom) in 0..1 space.
    // Row heights tuned for 466px round display with minimal clipping.

    private fun leftBox(row: Int)  = RectF(0.05f, row * 0.095f + 0.36f, 0.46f, row * 0.095f + 0.44f)
    private fun rightBox(row: Int) = RectF(0.54f, row * 0.095f + 0.36f, 0.95f, row * 0.095f + 0.44f)

    private val bounds = mapOf(
        // top corners — above clock
        BATTERY       to RectF(0.04f, 0.04f, 0.38f, 0.14f),
        NOTIFICATIONS to RectF(0.62f, 0.04f, 0.96f, 0.14f),

        // data grid — 5 rows × 2 columns, below clock
        HEART_RATE    to leftBox(0),
        TEMPERATURE   to rightBox(0),
        SPO2          to leftBox(1),
        WEATHER       to rightBox(1),
        STEPS         to leftBox(2),
        CALORIES      to rightBox(2),
        DISTANCE      to leftBox(3),
        UV_INDEX      to rightBox(3),
        SLEEP         to leftBox(4),
        STRESS        to rightBox(4),

        // bottom strip
        ALARM         to RectF(0.04f, 0.855f, 0.35f, 0.935f),
        WORLD_CLOCK   to RectF(0.38f, 0.855f, 0.62f, 0.935f),
        SUNRISE       to RectF(0.65f, 0.855f, 0.96f, 0.935f),

        // very bottom center
        FLOORS        to RectF(0.30f, 0.935f, 0.70f, 1.00f),
    )

    fun createComplicationSlotsManager(
        context: Context,
        currentUserStyleRepository: CurrentUserStyleRepository,
    ): ComplicationSlotsManager {

        fun factory(id: Int): CanvasComplicationFactory =
            CanvasComplicationFactory { watchState, invalidateCallback ->
                val drawable = ComplicationDrawable.getDrawable(context, R.drawable.complication_style)!!
                CanvasComplicationDrawable(drawable, watchState, invalidateCallback)
            }

        fun defaultPolicy(source: Int, vararg fallback: Int) =
            DefaultComplicationDataSourcePolicy(
                source,
                *fallback.toTypedArray(),
                defaultDataSourceType = ComplicationType.SHORT_TEXT
            )

        val slots = listOf(
            buildSlot(BATTERY,       factory(BATTERY),       SHORT_TEXT_TYPES,
                defaultPolicy(SystemDataSources.DATA_SOURCE_WATCH_BATTERY)),

            buildSlot(NOTIFICATIONS, factory(NOTIFICATIONS), SHORT_TEXT_TYPES,
                defaultPolicy(SystemDataSources.DATA_SOURCE_UNREAD_NOTIFICATION_COUNT)),

            buildSlot(HEART_RATE,    factory(HEART_RATE),    SHORT_TEXT_TYPES,
                defaultPolicy(SystemDataSources.DATA_SOURCE_HEART_RATE)),

            buildSlot(TEMPERATURE,   factory(TEMPERATURE),   SHORT_TEXT_TYPES,
                DefaultComplicationDataSourcePolicy(ComplicationType.SHORT_TEXT)),

            buildSlot(SPO2,          factory(SPO2),          SHORT_TEXT_TYPES,
                DefaultComplicationDataSourcePolicy(ComplicationType.SHORT_TEXT)),

            buildSlot(WEATHER,       factory(WEATHER),       SHORT_TEXT_TYPES,
                DefaultComplicationDataSourcePolicy(ComplicationType.SHORT_TEXT)),

            buildSlot(STEPS,         factory(STEPS),         SHORT_TEXT_TYPES,
                defaultPolicy(SystemDataSources.DATA_SOURCE_STEP_COUNT)),

            buildSlot(CALORIES,      factory(CALORIES),      SHORT_TEXT_TYPES,
                defaultPolicy(SystemDataSources.DATA_SOURCE_WATCH_BATTERY)),  // placeholder

            buildSlot(DISTANCE,      factory(DISTANCE),      SHORT_TEXT_TYPES,
                DefaultComplicationDataSourcePolicy(ComplicationType.SHORT_TEXT)),

            buildSlot(UV_INDEX,      factory(UV_INDEX),      SHORT_TEXT_TYPES,
                DefaultComplicationDataSourcePolicy(ComplicationType.SHORT_TEXT)),

            buildSlot(SLEEP,         factory(SLEEP),         SHORT_TEXT_TYPES,
                defaultPolicy(SystemDataSources.DATA_SOURCE_SUNRISE_SUNSET)),  // placeholder

            buildSlot(STRESS,        factory(STRESS),        SHORT_TEXT_TYPES,
                DefaultComplicationDataSourcePolicy(ComplicationType.SHORT_TEXT)),

            buildSlot(ALARM,         factory(ALARM),         SHORT_TEXT_TYPES,
                defaultPolicy(SystemDataSources.DATA_SOURCE_NEXT_EVENT)),

            buildSlot(WORLD_CLOCK,   factory(WORLD_CLOCK),   LONG_TEXT_TYPES,
                defaultPolicy(SystemDataSources.DATA_SOURCE_TIME_AND_DATE)),

            buildSlot(SUNRISE,       factory(SUNRISE),       SHORT_TEXT_TYPES,
                defaultPolicy(SystemDataSources.DATA_SOURCE_SUNRISE_SUNSET)),

            buildSlot(FLOORS,        factory(FLOORS),        SHORT_TEXT_TYPES,
                DefaultComplicationDataSourcePolicy(ComplicationType.SHORT_TEXT)),
        )

        return ComplicationSlotsManager(slots, currentUserStyleRepository)
    }

    private fun buildSlot(
        id: Int,
        factory: CanvasComplicationFactory,
        types: List<ComplicationType>,
        policy: DefaultComplicationDataSourcePolicy,
    ): ComplicationSlot = ComplicationSlot.createRoundRectComplicationSlotBuilder(
        id = id,
        canvasComplicationFactory = factory,
        supportedTypes = types,
        defaultDataSourcePolicy = policy,
        bounds = ComplicationSlotBounds(bounds.getValue(id)),
    ).build()
}
