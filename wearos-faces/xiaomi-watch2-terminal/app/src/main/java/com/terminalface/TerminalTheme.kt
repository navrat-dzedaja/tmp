package com.terminalface

import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface

/** All visual parameters for one colour theme. */
data class TerminalTheme(
    val background: Int,
    val primary: Int,       // time, main values
    val secondary: Int,     // labels, borders
    val dim: Int,           // decorators, progress track
    val accent: Int,        // hostname / header line
    val warning: Int,       // values above 80 %
    val critical: Int,      // values above 95 % / errors
) {
    companion object {
        val MATRIX_GREEN = TerminalTheme(
            background = Color.parseColor("#000000"),
            primary    = Color.parseColor("#00FF41"),
            secondary  = Color.parseColor("#00CC34"),
            dim        = Color.parseColor("#005510"),
            accent     = Color.parseColor("#00FFFF"),
            warning    = Color.parseColor("#FFFF00"),
            critical   = Color.parseColor("#FF4444"),
        )
        val AMBER = TerminalTheme(
            background = Color.parseColor("#0A0500"),
            primary    = Color.parseColor("#FFB000"),
            secondary  = Color.parseColor("#CC8800"),
            dim        = Color.parseColor("#553C00"),
            accent     = Color.parseColor("#FFD700"),
            warning    = Color.parseColor("#FF8800"),
            critical   = Color.parseColor("#FF3300"),
        )
        val CYAN = TerminalTheme(
            background = Color.parseColor("#000A0A"),
            primary    = Color.parseColor("#00FFFF"),
            secondary  = Color.parseColor("#00AAAA"),
            dim        = Color.parseColor("#004444"),
            accent     = Color.parseColor("#00FF88"),
            warning    = Color.parseColor("#FFFF00"),
            critical   = Color.parseColor("#FF5555"),
        )
        val RED_ALERT = TerminalTheme(
            background = Color.parseColor("#080000"),
            primary    = Color.parseColor("#FF3333"),
            secondary  = Color.parseColor("#CC1111"),
            dim        = Color.parseColor("#440000"),
            accent     = Color.parseColor("#FF8800"),
            warning    = Color.parseColor("#FFAA00"),
            critical   = Color.parseColor("#FF0000"),
        )
        val PAPER_WHITE = TerminalTheme(
            background = Color.parseColor("#F0F0F0"),
            primary    = Color.parseColor("#111111"),
            secondary  = Color.parseColor("#333333"),
            dim        = Color.parseColor("#BBBBBB"),
            accent     = Color.parseColor("#0055BB"),
            warning    = Color.parseColor("#CC7700"),
            critical   = Color.parseColor("#CC0000"),
        )

        val ALL = listOf(MATRIX_GREEN, AMBER, CYAN, RED_ALERT, PAPER_WHITE)
        val NAMES = listOf("Matrix Green", "Amber CRT", "Cyan Terminal", "Red Alert", "Paper White")
    }
}

/** Pre-built Paint objects derived from a theme. Updates in place when theme changes. */
class TerminalPaints(private var theme: TerminalTheme, private val typeface: Typeface) {

    fun updateTheme(newTheme: TerminalTheme) { theme = newTheme; rebuild() }

    // ── Public paint objects ────────────────────────────────────────────
    val bg         = Paint()
    val timePaint  = Paint(Paint.ANTI_ALIAS_FLAG)
    val datePaint  = Paint(Paint.ANTI_ALIAS_FLAG)
    val labelPaint = Paint(Paint.ANTI_ALIAS_FLAG)
    val valuePaint = Paint(Paint.ANTI_ALIAS_FLAG)
    val accentPaint = Paint(Paint.ANTI_ALIAS_FLAG)
    val dimPaint   = Paint(Paint.ANTI_ALIAS_FLAG)
    val barFull    = Paint(Paint.ANTI_ALIAS_FLAG)
    val barEmpty   = Paint(Paint.ANTI_ALIAS_FLAG)
    val sepPaint   = Paint(Paint.ANTI_ALIAS_FLAG)
    val secDotPaint = Paint(Paint.ANTI_ALIAS_FLAG)
    val ambientTimePaint  = Paint(Paint.ANTI_ALIAS_FLAG)
    val ambientLabelPaint = Paint(Paint.ANTI_ALIAS_FLAG)

    init { rebuild() }

    private fun rebuild() {
        bg.color = theme.background
        bg.style = Paint.Style.FILL

        timePaint.apply {
            color     = theme.primary
            typeface  = this@TerminalPaints.typeface
            textSize  = 72f
            textAlign = Paint.Align.CENTER
        }
        datePaint.apply {
            color     = theme.accent
            typeface  = this@TerminalPaints.typeface
            textSize  = 22f
            textAlign = Paint.Align.CENTER
        }
        labelPaint.apply {
            color     = theme.secondary
            typeface  = this@TerminalPaints.typeface
            textSize  = 17f
            textAlign = Paint.Align.LEFT
        }
        valuePaint.apply {
            color     = theme.primary
            typeface  = this@TerminalPaints.typeface
            textSize  = 17f
            textAlign = Paint.Align.LEFT
        }
        accentPaint.apply {
            color     = theme.accent
            typeface  = this@TerminalPaints.typeface
            textSize  = 18f
            textAlign = Paint.Align.CENTER
        }
        dimPaint.apply {
            color     = theme.dim
            typeface  = this@TerminalPaints.typeface
            textSize  = 17f
            textAlign = Paint.Align.LEFT
        }
        barFull.apply {
            color = theme.primary
            style = Paint.Style.FILL
        }
        barEmpty.apply {
            color = theme.dim
            style = Paint.Style.FILL
        }
        sepPaint.apply {
            color       = theme.secondary
            style       = Paint.Style.STROKE
            strokeWidth = 1f
        }
        secDotPaint.apply {
            color = theme.accent
            style = Paint.Style.FILL
        }
        ambientTimePaint.apply {
            color     = theme.secondary
            typeface  = this@TerminalPaints.typeface
            textSize  = 72f
            textAlign = Paint.Align.CENTER
            style     = Paint.Style.STROKE
            strokeWidth = 1.5f
        }
        ambientLabelPaint.apply {
            color     = theme.dim
            typeface  = this@TerminalPaints.typeface
            textSize  = 15f
            textAlign = Paint.Align.LEFT
        }
    }

    fun valueColorFor(fraction: Float): Int = when {
        fraction >= 0.95f -> theme.critical
        fraction >= 0.80f -> theme.warning
        else              -> theme.primary
    }
}
