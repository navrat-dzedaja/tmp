# Wear OS watch face classes must not be stripped
-keep class com.terminalface.** { *; }
-keep class androidx.wear.watchface.** { *; }

# Kotlin metadata
-keepattributes *Annotation*, Signature, InnerClasses, EnclosingMethod
