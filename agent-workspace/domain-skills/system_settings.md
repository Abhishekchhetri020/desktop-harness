# System Settings skill

System Settings (formerly Preferences) on Ventura+ is a SwiftUI-based app
with deep AX support. Use AX to navigate panes and toggles.

## Open a specific pane via URL

```python
import subprocess
# Privacy → Accessibility
subprocess.run(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"])
# Privacy → Screen Recording
subprocess.run(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"])
# Privacy → Input Monitoring
subprocess.run(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent"])
# Privacy → Automation
subprocess.run(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Automation"])
# Bluetooth
subprocess.run(["open", "x-apple.systempreferences:com.apple.BluetoothSettings"])
# Wallpaper
subprocess.run(["open", "x-apple.systempreferences:com.apple.WallpaperSettings.WallpaperSettings"])
```

## Toggle a switch by accessible name

```python
activate("System Settings")
sw = find("System Settings", role="AXSwitch", title="Bluetooth")
click_element(sw)
```

## Search via the sidebar search field

```python
activate("System Settings")
sf = find("System Settings", role="AXTextField", subrole="AXSearchField")
focus(sf); type_text("display"); key("return")
```
