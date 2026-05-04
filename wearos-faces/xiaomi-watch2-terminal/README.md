# Terminal Watch Face — Xiaomi Smart Watch 2

A **conky / htop-inspired** watch face for the **Xiaomi Smart Watch 2**
(466 × 466 px AMOLED, Wear OS 3.5).

```
root@xiaomi-watch2:~ #
──────────────────────────────────────
        23:45:12
     MON  2026-05-04
──────── SENSOR READOUT ────────────
HR  : [████████░░]  72 bpm   TEMP: 22°C
SPO2: [█████████░]  98%      WTHR: ⛅
STEP: [███░░░░░░░]  8,234    CAL : 432
DIST: [███░░░░░░░]  3.2 km   UV  : 3
SLEP: [████████░░]  7h23m    STRS: LOW
──────────────────────────────────────
 [BATT  78%]             [NOTIF  5]
 [ALM 07:30] [TZ2 NYC 17:45] [SUN ↑06:12]
          [FLOOR  12 flrs]
──────────────────────────────────────
     terminal-watchface // xiaomi-watch2
```

## Complication slots (16 total)

| # | Slot        | Default data source           |
|---|-------------|-------------------------------|
| 1 | BATT        | Watch battery                 |
| 2 | NOTIF       | Unread notifications          |
| 3 | HR          | Heart rate                    |
| 4 | TEMP        | *(set manually — weather app)*|
| 5 | SPO2        | Blood oxygen                  |
| 6 | WTHR        | *(set manually — weather app)*|
| 7 | STEP        | Step count                    |
| 8 | CAL         | *(set manually — fitness app)*|
| 9 | DIST        | *(set manually — fitness app)*|
|10 | UV          | *(set manually — weather app)*|
|11 | SLEP        | *(set manually — sleep app)*  |
|12 | STRS        | *(set manually — health app)* |
|13 | ALM         | Next alarm / event            |
|14 | TZ2         | World clock (2nd timezone)    |
|15 | SUN         | Sunrise / sunset              |
|16 | FLOOR       | *(set manually — fitness app)*|

Slots without a system default must be configured on the watch via
**long-press → Edit watch face → tap a slot**.

## Colour themes

| Theme        | Description                        |
|--------------|------------------------------------|
| Matrix Green | Classic #00FF41 on black (default) |
| Amber CRT    | Warm amber, vintage monitor feel   |
| Cyan Terminal| Cyan/teal — cooler blue-green      |
| Red Alert    | Red on near-black                  |
| Paper White  | Dark text on light grey            |

Switch themes: **long-press → Edit watch face → Style**.

---

## Building

### Prerequisites

| Tool            | Version |
|-----------------|---------|
| Android Studio  | Hedgehog or newer |
| JDK             | 17      |
| Android SDK     | API 34  |
| Wear OS emulator or physical device | Wear OS 3.x |

### Steps

```bash
# 1 — open the project
cd wearos-faces/xiaomi-watch2-terminal
# open in Android Studio, or:

# 2 — build the debug APK from the command line
./gradlew assembleDebug
# APK output: app/build/outputs/apk/debug/app-debug.apk
```

---

## Installing on the Xiaomi Smart Watch 2

### Via Android Studio (easiest)

1. Enable **Developer options** on the watch:
   - Settings → About → tap **Build number** 7 times
2. Enable **ADB debugging**:
   - Settings → Developer options → ADB debugging → ON
3. Connect the watch to the same Wi-Fi as your PC (or pair via Bluetooth).
4. In Android Studio select the watch as the run target → **Run ▶**.

### Via ADB over Wi-Fi (no cable needed)

```bash
# Find the watch IP: Settings → About → Status → IP address
ADB_IP=192.168.1.XX   # ← replace

adb connect $ADB_IP:5555
adb install app/build/outputs/apk/debug/app-debug.apk

# After install, choose the face on the watch:
# Settings → Watch face → select "Terminal // CONKY"
```

### Via ADB over Bluetooth (Wear OS companion app)

1. Open the **Wear OS** companion app on your phone.
2. Enable **Developer options** in the app.
3. Turn on **Debugging over Bluetooth**.
4. On your PC:

```bash
adb forward tcp:4444 localabstract:/adb-hub
adb connect localhost:4444
adb -s localhost:4444 install app/build/outputs/apk/debug/app-debug.apk
```

---

## Configuring complication slots on the watch

1. Long-press the watch face.
2. Tap **Edit watch face** (pencil icon).
3. Tap any highlighted slot.
4. Choose a data source from the list (e.g. Weather, Health, etc.).
5. Press the back button to save.

For slots that say "No data source" (TEMP, SPO2, etc.), you need a
third-party app that provides that complication type installed on the watch.
Good options:
- **Complications Suite** (Wear OS, free)
- **WearOS Data Layer** (pulls data from paired phone)
- Any health/weather app that publishes Wear OS complications

---

## Project structure

```
xiaomi-watch2-terminal/
├── app/src/main/
│   ├── AndroidManifest.xml
│   ├── java/com/terminalface/
│   │   ├── TerminalWatchFaceService.kt   ← service entry point
│   │   ├── TerminalRenderer.kt           ← all Canvas drawing
│   │   ├── ComplicationConfig.kt         ← 16 complication slots
│   │   ├── TerminalTheme.kt              ← themes + Paint objects
│   │   ├── TerminalStyleSchema.kt        ← user style schema
│   │   └── config/
│   │       └── WatchFaceConfigActivity.kt← theme picker UI
│   └── res/
│       ├── drawable/
│       │   ├── complication_style.xml
│       │   ├── ic_launcher.xml
│       │   └── preview_terminal.xml
│       ├── values/
│       │   ├── colors.xml
│       │   └── strings.xml
│       └── xml/
│           └── watch_face.xml
├── app/build.gradle.kts
├── build.gradle.kts
└── settings.gradle.kts
```
