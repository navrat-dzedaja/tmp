package com.terminalface

import android.content.Context
import android.graphics.*
import android.view.SurfaceHolder
import androidx.wear.watchface.*
import androidx.wear.watchface.complications.data.*
import androidx.wear.watchface.style.CurrentUserStyleRepository
import androidx.wear.watchface.style.UserStyle
import androidx.wear.watchface.style.UserStyleSetting
import java.time.Instant
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

/**
 * Canvas renderer — draws the full terminal/conky UI.
 *
 * Target: Xiaomi Smart Watch 2 — 466 × 466 px AMOLED round display.
 *
 * Design: htop / conky aesthetic — monospace text, ASCII separators,
 * block progress bars, colour-coded values by severity.
 *
 * Ambient: stroke-only clock + battery; minimal pixel illumination.
 */
class TerminalRenderer(
    private val context: Context,
    surfaceHolder: SurfaceHolder,
    // stored as private val so updateThemeFromStyle() can access the schema
    private val currentUserStyleRepository: CurrentUserStyleRepository,
    watchState: WatchState,
    private val complicationSlotsManager: ComplicationSlotsManager,
    canvasType: Int,
) : Renderer.CanvasRenderer2<TerminalRenderer.Assets>(
    surfaceHolder                                        = surfaceHolder,
    currentUserStyleRepository                           = currentUserStyleRepository,
    watchState                                           = watchState,
    canvasType                                           = canvasType,
    interactiveDrawModeUpdateDelayMillis                 = 100L,
    clearWithBackgroundTintBeforeRenderingHighlightLayer = false,
) {

    private val mono: Typeface = Typeface.create("monospace", Typeface.NORMAL)

    private var currentTheme = TerminalTheme.MATRIX_GREEN
    private val p = TerminalPaints(currentTheme, mono)

    private val timeFmt  = DateTimeFormatter.ofPattern("HH:mm:ss")
    private val timeFmtA = DateTimeFormatter.ofPattern("HH:mm")
    private val dateFmt  = DateTimeFormatter.ofPattern("EEE  yyyy-MM-dd")

    // ── Style observation ──────────────────────────────────────────────────
    // CanvasRenderer2 does not expose onUserStyleChanged(); observe the flow
    // directly on a dedicated scope and cancel it in onDestroy().
    private val styleScope = CoroutineScope(Dispatchers.Main.immediate + SupervisorJob())

    init {
        styleScope.launch {
            currentUserStyleRepository.userStyle.collect { updateThemeFromStyle(it) }
        }
    }

    private fun updateThemeFromStyle(style: UserStyle) {
        val setting = currentUserStyleRepository.schema.userStyleSettings
            .filterIsInstance<UserStyleSetting.ListUserStyleSetting>()
            .firstOrNull { it.id == TerminalStyleSchema.COLOR_STYLE_SETTING } ?: return
        // style[UserStyleSetting] is unambiguous (vs style[UserStyleSetting.Id])
        val opt = style[setting] as? UserStyleSetting.ListUserStyleSetting.ListOption ?: return
        val idx = TerminalTheme.NAMES.indexOf(opt.displayName.toString())
        currentTheme = TerminalTheme.ALL.getOrElse(idx) { TerminalTheme.MATRIX_GREEN }
        p.updateTheme(currentTheme)
    }

    override fun onDestroy() {
        super.onDestroy()
        styleScope.cancel()
    }

    // ── Shared assets ──────────────────────────────────────────────────────
    class Assets : SharedAssets { override fun onDestroy() {} }
    override suspend fun createSharedAssets(): Assets = Assets()

    // ══════════════════════════════════════════════════════════════════════
    //  Render
    // ══════════════════════════════════════════════════════════════════════

    override fun render(
        canvas: Canvas,
        bounds: Rect,
        zonedDateTime: ZonedDateTime,
        sharedAssets: Assets,
    ) {
        val cx      = bounds.exactCenterX()
        val cy      = bounds.exactCenterY()
        val w       = bounds.width().toFloat()
        val h       = bounds.height().toFloat()
        val ambient = renderParameters.drawMode == DrawMode.AMBIENT

        drawBackground(canvas, bounds, ambient)
        if (ambient) drawAmbient(canvas, cx, cy, w, h, zonedDateTime)
        else         drawInteractive(canvas, cx, cy, w, h, zonedDateTime)
    }

    override fun renderHighlightLayer(
        canvas: Canvas,
        bounds: Rect,
        zonedDateTime: ZonedDateTime,
        sharedAssets: Assets,
    ) {
        complicationSlotsManager.complicationSlots.values.forEach { slot ->
            if (slot.enabled) slot.renderHighlightLayer(canvas, zonedDateTime, renderParameters)
        }
    }

    // ── Background ─────────────────────────────────────────────────────────
    private val scanPaint = Paint().apply { color = Color.argb(20, 0, 0, 0); style = Paint.Style.FILL }

    private fun drawBackground(canvas: Canvas, bounds: Rect, ambient: Boolean) {
        if (ambient) { canvas.drawColor(Color.BLACK); return }
        canvas.drawRect(bounds, p.bg)
        var y = 0f
        while (y < bounds.height()) { canvas.drawRect(0f, y, bounds.width().toFloat(), y + 1f, scanPaint); y += 4f }
    }

    // ── Interactive ─────────────────────────────────────────────────────────
    private fun drawInteractive(canvas: Canvas, cx: Float, cy: Float, w: Float, h: Float, dt: ZonedDateTime) {
        val lEdge = w * 0.065f
        val rEdge = w * 0.935f

        p.accentPaint.textSize = 15f
        canvas.drawText("root@watch2:~ #", cx, h * 0.075f, p.accentPaint)
        drawHSep(canvas, lEdge, rEdge, h * 0.09f)

        p.timePaint.textSize = 68f
        canvas.drawText(dt.format(timeFmt), cx, h * 0.225f, p.timePaint)

        p.datePaint.textSize = 20f
        canvas.drawText(dt.format(dateFmt).uppercase(), cx, h * 0.272f, p.datePaint)
        drawHSep(canvas, lEdge, rEdge, h * 0.29f)

        p.accentPaint.textSize = 12f
        canvas.drawText("──[ SENSOR READOUT ]──", cx, h * 0.315f, p.accentPaint)

        val lLbl = lEdge
        val lBar = lEdge + w * 0.115f
        val lVal = lEdge + w * 0.26f
        val rLbl = cx + w * 0.025f
        val rBar = cx + w * 0.14f
        val rVal = cx + w * 0.285f

        data class Row(val leftId: Int, val rightId: Int, val y: Float)
        val dataRows = listOf(
            Row(ComplicationConfig.HEART_RATE,  ComplicationConfig.TEMPERATURE, h * 0.362f),
            Row(ComplicationConfig.SPO2,         ComplicationConfig.WEATHER,     h * 0.427f),
            Row(ComplicationConfig.STEPS,        ComplicationConfig.CALORIES,    h * 0.492f),
            Row(ComplicationConfig.DISTANCE,     ComplicationConfig.UV_INDEX,    h * 0.557f),
            Row(ComplicationConfig.SLEEP,        ComplicationConfig.STRESS,      h * 0.622f),
        )
        val labels = mapOf(
            ComplicationConfig.HEART_RATE  to "HR  :",
            ComplicationConfig.TEMPERATURE to "TEMP:",
            ComplicationConfig.SPO2        to "SPO2:",
            ComplicationConfig.WEATHER     to "WTHR:",
            ComplicationConfig.STEPS       to "STEP:",
            ComplicationConfig.CALORIES    to "CAL :",
            ComplicationConfig.DISTANCE    to "DIST:",
            ComplicationConfig.UV_INDEX    to "UV  :",
            ComplicationConfig.SLEEP       to "SLEP:",
            ComplicationConfig.STRESS      to "STRS:",
        )

        for (row in dataRows) {
            p.labelPaint.textSize = 15f
            p.valuePaint.textSize = 15f
            canvas.drawText(labels[row.leftId]  ?: "", lLbl, row.y, p.labelPaint)
            drawInlineComp(canvas, row.leftId,  lBar, lVal, row.y)
            canvas.drawText(labels[row.rightId] ?: "", rLbl, row.y, p.labelPaint)
            drawInlineComp(canvas, row.rightId, rBar, rVal, row.y)
        }

        drawHSep(canvas, lEdge, rEdge, h * 0.655f)

        drawBlockComp(canvas, ComplicationConfig.BATTERY,
            lEdge, h * 0.665f, cx - w * 0.03f, h * 0.725f, "BATT")
        drawBlockComp(canvas, ComplicationConfig.NOTIFICATIONS,
            cx + w * 0.03f, h * 0.665f, rEdge, h * 0.725f, "NOTIF")

        drawBlockComp(canvas, ComplicationConfig.ALARM,
            lEdge,     h * 0.735f, w * 0.36f, h * 0.795f, "ALM")
        drawBlockComp(canvas, ComplicationConfig.WORLD_CLOCK,
            w * 0.37f, h * 0.735f, w * 0.63f, h * 0.795f, "TZ2")
        drawBlockComp(canvas, ComplicationConfig.SUNRISE,
            w * 0.64f, h * 0.735f, rEdge,     h * 0.795f, "SUN")

        drawBlockComp(canvas, ComplicationConfig.FLOORS,
            w * 0.27f, h * 0.805f, w * 0.73f, h * 0.865f, "FLOOR")

        p.dimPaint.textAlign = Paint.Align.CENTER
        p.dimPaint.textSize  = 10f
        canvas.drawText("terminal-watchface  //  xiaomi-watch2", cx, h * 0.955f, p.dimPaint)
    }

    // ── Complication helpers ───────────────────────────────────────────────

    private fun drawInlineComp(canvas: Canvas, slotId: Int, barX: Float, valX: Float, rowY: Float) {
        val slot = complicationSlotsManager.complicationSlots[slotId] ?: return
        val (fraction, text) = extractData(slot.complicationData.value)

        val barW = 38f; val barH = 7f; val barTop = rowY - barH - 2f
        canvas.drawRect(barX, barTop, barX + barW, rowY - 2f, p.barEmpty)
        if (fraction > 0f) {
            p.barFull.color = p.valueColorFor(fraction)
            canvas.drawRect(barX, barTop, barX + barW * fraction, rowY - 2f, p.barFull)
        }
        p.valuePaint.color     = p.valueColorFor(fraction)
        p.valuePaint.textAlign = Paint.Align.LEFT
        canvas.drawText(text, valX, rowY, p.valuePaint)
        p.valuePaint.color = currentTheme.primary
    }

    private fun drawBlockComp(
        canvas: Canvas, slotId: Int,
        left: Float, top: Float, right: Float, bottom: Float, label: String,
    ) {
        val slot = complicationSlotsManager.complicationSlots[slotId] ?: return
        val (_, text) = extractData(slot.complicationData.value)

        canvas.drawRect(RectF(left, top, right, bottom), p.sepPaint)
        p.dimPaint.textAlign = Paint.Align.LEFT
        p.dimPaint.textSize  = 10f
        canvas.drawText(label, left + 3f, top + 11f, p.dimPaint)
        p.valuePaint.textSize  = 13f
        p.valuePaint.textAlign = Paint.Align.CENTER
        canvas.drawText(text, (left + right) / 2f, (top + bottom) / 2f + 5f, p.valuePaint)
        p.valuePaint.textSize  = 15f
        p.valuePaint.textAlign = Paint.Align.LEFT
    }

    // ── Complication data extraction ───────────────────────────────────────
    // getTextAt() takes Instant in watchface 1.2.x, not Long.

    private fun extractData(data: ComplicationData): Pair<Float, String> {
        val res = context.resources
        val now = Instant.now()
        return when (data) {
            is ShortTextComplicationData -> {
                val value = data.text.getTextAt(res, now).toString()
                val title = data.title?.getTextAt(res, now)?.toString().orEmpty()
                val display = if (title.isNotEmpty()) "$value $title" else value
                Pair(0.5f, display.take(9))
            }
            is RangedValueComplicationData -> {
                val range = data.max - data.min
                val frac  = if (range > 0f) (data.value - data.min) / range else 0f
                val text  = data.text?.getTextAt(res, now)?.toString()
                    ?: "%.0f%%".format(frac * 100)
                Pair(frac.coerceIn(0f, 1f), text.take(9))
            }
            is LongTextComplicationData -> {
                val text = data.text.getTextAt(res, now).toString()
                Pair(0f, text.take(10))
            }
            is NoDataComplicationData,
            is NotConfiguredComplicationData -> Pair(0f, "---")
            else -> Pair(0f, "?")
        }
    }

    // ── Ambient ────────────────────────────────────────────────────────────

    private fun drawAmbient(canvas: Canvas, cx: Float, cy: Float, w: Float, h: Float, dt: ZonedDateTime) {
        canvas.drawText(dt.format(timeFmtA), cx, cy + 15f, p.ambientTimePaint)
        p.ambientLabelPaint.textAlign = Paint.Align.CENTER
        p.ambientLabelPaint.textSize  = 18f
        canvas.drawText(dt.format(dateFmt).uppercase(), cx, cy + 50f, p.ambientLabelPaint)

        complicationSlotsManager.complicationSlots[ComplicationConfig.BATTERY]?.let {
            val (_, text) = extractData(it.complicationData.value)
            p.ambientLabelPaint.textSize  = 13f
            p.ambientLabelPaint.textAlign = Paint.Align.RIGHT
            canvas.drawText("BATT $text", w * 0.92f, h * 0.14f, p.ambientLabelPaint)
        }
        complicationSlotsManager.complicationSlots[ComplicationConfig.STEPS]?.let {
            val (_, text) = extractData(it.complicationData.value)
            p.ambientLabelPaint.textSize  = 13f
            p.ambientLabelPaint.textAlign = Paint.Align.LEFT
            canvas.drawText("STEP $text", w * 0.08f, h * 0.86f, p.ambientLabelPaint)
        }
        complicationSlotsManager.complicationSlots[ComplicationConfig.HEART_RATE]?.let {
            val (_, text) = extractData(it.complicationData.value)
            p.ambientLabelPaint.textSize  = 13f
            p.ambientLabelPaint.textAlign = Paint.Align.RIGHT
            canvas.drawText("HR $text", w * 0.92f, h * 0.86f, p.ambientLabelPaint)
        }
    }

    private fun drawHSep(canvas: Canvas, x1: Float, x2: Float, y: Float) =
        canvas.drawLine(x1, y, x2, y, p.sepPaint)
}
