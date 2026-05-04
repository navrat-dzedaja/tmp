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

    private val SHORT_TEXT_TYPES = listOf(
        ComplicationType.SHORT_TEXT,
        ComplicationType.RANGED_VALUE,
        ComplicationType.SMALL_IMAGE,
    )
    private val LONG_TEXT_TYPES = listOf(
        ComplicationType.LONG_TEXT,
        ComplicationType.SHORT_TEXT,
    )

    // ── Complication bounds in 0..1 normalised space ───────────────────────
    private fun leftBox(row: Int)  = RectF(0.05f, row * 0.095f + 0.36f, 0.46f, row * 0.095f + 0.44f)
    private fun rightBox(row: Int) = RectF(0.54f, row * 0.095f + 0.36f, 0.95f, row * 0.095f + 0.44f)

    private val bounds = mapOf(
        BATTERY       to RectF(0.04f, 0.04f, 0.38f, 0.14f),
        NOTIFICATIONS to RectF(0.62f, 0.04f, 0.96f, 0.14f),
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
        ALARM         to RectF(0.04f, 0.855f, 0.35f, 0.935f),
        WORLD_CLOCK   to RectF(0.38f, 0.855f, 0.62f, 0.935f),
        SUNRISE       to RectF(0.65f, 0.855f, 0.96f, 0.935f),
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

        // Slots with a known system data source
        fun systemPolicy(source: Int) =
            DefaultComplicationDataSourcePolicy(source, ComplicationType.SHORT_TEXT)

        // Slots the user must configure themselves (no system fallback)
        fun emptyPolicy() = DefaultComplicationDataSourcePolicy()

        val slots = listOf(
            buildSlot(BATTERY,       factory(BATTERY),       SHORT_TEXT_TYPES,
                systemPolicy(SystemDataSources.DATA_SOURCE_WATCH_BATTERY)),

            buildSlot(NOTIFICATIONS, factory(NOTIFICATIONS), SHORT_TEXT_TYPES,
                systemPolicy(SystemDataSources.DATA_SOURCE_UNREAD_NOTIFICATION_COUNT)),

            // DATA_SOURCE_HEART_RATE does not exist in SystemDataSources 1.2.x;
            // heart rate must be sourced from a health app chosen by the user.
            buildSlot(HEART_RATE,    factory(HEART_RATE),    SHORT_TEXT_TYPES,
                emptyPolicy()),

            buildSlot(TEMPERATURE,   factory(TEMPERATURE),   SHORT_TEXT_TYPES,
                emptyPolicy()),

            buildSlot(SPO2,          factory(SPO2),          SHORT_TEXT_TYPES,
                emptyPolicy()),

            buildSlot(WEATHER,       factory(WEATHER),       SHORT_TEXT_TYPES,
                emptyPolicy()),

            buildSlot(STEPS,         factory(STEPS),         SHORT_TEXT_TYPES,
                systemPolicy(SystemDataSources.DATA_SOURCE_STEP_COUNT)),

            buildSlot(CALORIES,      factory(CALORIES),      SHORT_TEXT_TYPES,
                emptyPolicy()),

            buildSlot(DISTANCE,      factory(DISTANCE),      SHORT_TEXT_TYPES,
                emptyPolicy()),

            buildSlot(UV_INDEX,      factory(UV_INDEX),      SHORT_TEXT_TYPES,
                emptyPolicy()),

            buildSlot(SLEEP,         factory(SLEEP),         SHORT_TEXT_TYPES,
                emptyPolicy()),

            buildSlot(STRESS,        factory(STRESS),        SHORT_TEXT_TYPES,
                emptyPolicy()),

            buildSlot(ALARM,         factory(ALARM),         SHORT_TEXT_TYPES,
                systemPolicy(SystemDataSources.DATA_SOURCE_NEXT_EVENT)),

            buildSlot(WORLD_CLOCK,   factory(WORLD_CLOCK),   LONG_TEXT_TYPES,
                systemPolicy(SystemDataSources.DATA_SOURCE_TIME_AND_DATE)),

            buildSlot(SUNRISE,       factory(SUNRISE),       SHORT_TEXT_TYPES,
                systemPolicy(SystemDataSources.DATA_SOURCE_SUNRISE_SUNSET)),

            buildSlot(FLOORS,        factory(FLOORS),        SHORT_TEXT_TYPES,
                emptyPolicy()),
        )

        return ComplicationSlotsManager(slots, currentUserStyleRepository)
    }

    private fun buildSlot(
        id: Int,
        factory: CanvasComplicationFactory,
        types: List<ComplicationType>,
        policy: DefaultComplicationDataSourcePolicy,
    ): ComplicationSlot = ComplicationSlot.createRoundRectComplicationSlotBuilder(
        id                       = id,
        canvasComplicationFactory = factory,
        supportedTypes           = types,
        defaultDataSourcePolicy  = policy,
        bounds                   = ComplicationSlotBounds(bounds.getValue(id)),
    ).build()
}
