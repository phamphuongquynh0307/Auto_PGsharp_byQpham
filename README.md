# Auto Catch Pokemon for PGSharp

**English** | [Tiếng Việt](README.vi.md)

A Windows automation tool for catching Pokemon in Pokemon GO with PGSharp. It connects to an Android device through ADB and supports both regular and quick catch workflows.

> **Personal project.** This repository is public for reference only and does not accept external code contributions.

## Features

- **Automatic catching** — catches Pokemon shown in PGSharp's nearby feed.
- **Quick Catch without a PGSharp key** — uses Android touch control to throw the ball and exit the encounter quickly.
- **Editable throws** — adjust throw power and flick duration for different phones.
- **Manual calibration** — fine-tune touch coordinates when automatic scaling is not accurate enough.
- **Shundo hunting** — stop only for shiny or 100% IV Pokemon, depending on your settings.
- **Popup handling** — closes weather, speed, level-up, and PokeStop screens automatically.
- **Out-of-ball recovery** — pauses catching while AutoWalk continues searching for more items, then resumes automatically.
- **Discord alerts** — notifications for long spawn gaps, periodic reports, low battery, no balls, shiny encounters, and more.
- **Screen adaptation** — scales coordinates to match different Android screen sizes.

## Requirements

- A **Windows** PC.
- An **Android** phone with **Pokemon GO (PGSharp)** installed.
- The phone and PC connected to the **same Wi-Fi network**.

## Getting Started

### 1. Prepare the phone

1. Enable **Developer options** (usually: *Settings → About phone → tap Build number seven times*).
2. Enable **USB debugging** in Developer options.
3. Open **Pokemon GO (PGSharp)** and stay on the map screen.

### 2. Connect

**First connection:**

1. Connect the phone to the PC with a USB cable.
2. Open the app and click **Connect**.
3. The app switches the device to Wi-Fi debugging and remembers it.
4. Unplug the cable when the app confirms that it is safe to do so.

**Later connections:**

1. Open the app.
2. Select the saved phone or click **Connect**.
3. The app reconnects over Wi-Fi automatically.

### 3. Choose a mode

- **Catch Pokemon** — catches Pokemon from the nearby feed automatically.
- **Shundo** — hunts only shiny or 100% IV Pokemon according to your configuration.

Choose a catch style as well:

- **Regular Catch** — waits for the normal catch sequence.
- **Quick Catch (No Key)** — performs a quick-catch gesture without requiring a paid PGSharp key.

### 4. Run

Click **Run** to start, **Pause** to pause, or **Stop** to finish. Activity is shown in the log panel.

### 5. Settings

- **Discord webhook** — paste a Discord channel webhook URL to receive alerts.
- **Throw power** — increase or decrease the distance of the ball throw.
- **Quick Catch flick** — adjust how long the quick-catch finger gesture lasts.
- **Manual calibration** — use the coordinate controls if touches do not land correctly on your phone.
- **@ to first slot distance** — adjust the offset to the first Pokemon entry when needed.

## When You Run Out of Poke Balls

The app exits the encounter, sends a Discord notification, pauses catching for 10 minutes, and keeps AutoWalk active to collect more items. Catching then resumes automatically.

## Troubleshooting

| Problem | Solution |
|---|---|
| Phone is not detected | Confirm that **USB debugging** is enabled and both devices are on the **same Wi-Fi network**. |
| Connection drops | Click **Refresh** or select the phone again. |
| Touch coordinates are inaccurate | Open manual calibration and adjust the relevant points for your screen. |
| Ball throw is too weak or too strong | Adjust **Throw power** and test again. |
| Phone gets warm | Lower screen brightness, avoid charging when unnecessary, and enable the screen-dimming option for long sessions. |

## Tips

- Keep Pokemon GO on the **map screen** before clicking **Run**.
- Test one catch after changing throw or calibration settings.
- Long automation sessions can warm the phone; use moderate brightness and good ventilation.

## Community & Support

- Discord: <https://discord.gg/QXSfKKPpG6>
- Ko-fi: <https://ko-fi.com/qpham7286>

## License

Copyright © 2026 Qpham. **All Rights Reserved.**

- You may **view** the source code and **fork** the repository under GitHub's terms.
- You may not use, copy, modify, redistribute, or commercially exploit the code without the author's written permission.
- External pull requests will not be merged.

See [LICENSE](LICENSE) for details. To request permission, open an issue on GitHub.
