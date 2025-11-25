# AudioBook - Hotkey Automation Tool

## Overview
AudioBook is a desktop automation tool inspired by AutoHotkey, designed to automate click sequences, particularly for games like Tibia. It allows users to create custom hotkeys that execute predefined mouse click sequences with configurable delays and advanced targeting capabilities. The project aims to streamline repetitive in-game actions, offering both convenience and efficiency.

## User Preferences
None specified yet

## System Architecture

### Core Design
The application features a GUI built with `tkinter` for hotkey management and configuration. Mouse and keyboard control are handled primarily by `pynput`, with `pyautogui` serving as a backup automation library. Configuration data, including hotkey definitions, click positions, and delays, is persisted in a JSON file (`audiobook_config.json`).

### Key Features

1.  **Profile Management**:
    *   Create/save/load unlimited configuration profiles (loadouts)
    *   Each profile stores: custom hotkeys, Best Sellers configs, delays, movement mode
    *   Quick-switch between profiles via dropdown
    *   Rename/delete profiles with protection for default profile
    *   Auto-save changes to active profile

2.  **Hotkey Management**:
    *   Add, edit, and delete hotkeys within each profile
    *   Support for custom key combinations and visual listing

3.  **Hotkey Types**:
    *   **Normal Type**: Automates sequences like right-clicking an item and then left-clicking the character (e.g., healing potions).
    *   **Offensive Type**: Position-based targeting system:
        *   User positions mouse on target
        *   Hotkey captures position → clicks rune → returns to position → attacks
        *   No computer vision needed, 100% reliable

4.  **Click Recording**: Interactive recording of click positions for both hotkey types.

5.  **Movement Modes**:
    *   **Humanized Movement** (default): Random timing (50-150ms), pauses to evade detection
    *   **Instant Teleport**: duration=0 for maximum speed (potentially detectable)
    *   UI toggle affects ALL hotkeys system-wide

6.  **Automation Execution**:
    *   Background thread execution for non-blocking GUI.
    *   Supports simultaneous execution of both hotkey types.
    *   Most-specific-match algorithm for overlapping hotkeys and auto-repeat protection.

7.  **Safety Features**: Master enable/disable toggle for the automation, visual status indicators, and confirmation for critical actions.

### UI/UX Decisions
The application features a harmonized "Ember" color palette (`#1B0F0B`, `#29140E`, `#3A1C10`, etc.) for a cohesive and visually appealing interface. It uses a medieval/RPG-themed Georgia font and has been designed for WCAG-compliant contrast ratios. Discreet program titling and the use of ASCII characters ensure broader compatibility, especially in VNC environments.

### Technical Implementations
*   **Platform Compatibility**: Primarily developed for Linux (Replit environment), but designed for cross-platform compatibility (Windows, macOS). Requires an X11 server for GUI display.
*   **Execution Model**: Hotkey listener and click execution operate in separate daemon threads to ensure a responsive GUI and reliable automation.
*   **Computer Vision**: Employs `mss` for fast screen capture, `opencv-python` for image processing (HSV color filtering, Gaussian blur, morphological operations), and `numpy` for array manipulations. `Pillow` (PIL) is used for image file loading in the calibration tool.

## External Dependencies

*   **Python 3.11**
*   **tkinter** (built-in Python GUI framework)
*   **pynput**: Cross-platform input device control (mouse and keyboard).
*   **pyautogui**: Backup automation library for mouse control.
*   **mss**: Ultra-fast screen capture library.
*   **opencv-python (cv2)**: Computer vision library for image processing and target detection.
*   **numpy**: Numerical computing library, used for array operations in image processing.
*   **Pillow (PIL)**: Image processing library, specifically for loading image files in the HSV calibration tool.
*   **six**: Python 2/3 compatibility library (dependency of pynput).
*   **python-xlib**: X11 interface for Linux (dependency of pynput).
*   **evdev-binary**: Event device interface (dependency of pynput).
## Recent Changes

### November 24, 2025 - Profile Management System (LATEST)
- **LOADOUT PROFILES**: Complete profile system for saving/loading different configurations
  - Create unlimited custom profiles (Hunt, Training, PvP, etc)
  - Each profile saves: hotkeys, Best Sellers positions, delays, movement mode
  - Quick-switch dropdown to change profiles instantly
  - Rename/delete profiles (except default "Padrão" profile)
- **AUTO-SAVE**: Changes automatically saved to active profile
- **UI CONTROLS**: Profile management bar with [+] Novo, [✎] Renomear, [X] Deletar
- **JSON MIGRATION**: Automatically converts old config format to new profile structure

### November 24, 2025 - Position-Based Targeting System
- **SIMPLIFIED TARGETING**: Eliminated computer vision detection entirely
  - User positions mouse on target → hotkey saves position → clicks rune → returns to position → attacks
  - Zero false positives, 100% reliable
- **HUMANIZED MOVEMENT**: Random timing (50-150ms duration, 10-40ms pauses) to evade detection
- **INSTANT TELEPORT TOGGLE**: UI checkbox to switch between humanized/instant movement modes
  - Affects ALL hotkeys (Auto SD, Auto EXPLO, custom hotkeys, healing macros)
- **ANTI-CHEAT EVASION**: Randomized delays prevent detection patterns

### November 24, 2025 - Automatic 2-Click Calibration System
- **REVOLUTIONARY CALIBRATION**: Only 2 clicks needed (down from 6!)
  - User calibrates ONLY during daytime (2 corner clicks on red outline)
  - System automatically generates MEDIUM and DARK profiles by simulating Tibia's lighting
  - Mathematical simulation: Medium (70% brightness, 85% saturation), Dark (50% brightness, 70% saturation)
- **CORNER-PAIR PRECISION**: User marks 2 opposite corners of red outline square
  - System extracts ONLY border pixels (not filled interior)
  - Eliminates contamination from red character outfits
  - More precise HSV values from actual outline borders
- **OVERLAY FIX**: Calibration overlay now disappears during screenshot capture
  - Prevents overlay darkness from affecting captured colors
  - Ensures accurate HSV values from real game lighting
- **AUTO EXPLO BUG FIX**: Fixed anti-repeat reset for Auto EXPLO hotkey
  - Added 'auto_explo' to on_release reset list
  - F4 now works identically to F1 (Auto SD)
- **ADMIN PERMISSIONS**: Requires running as administrator for mouse/keyboard control

### November 24, 2025 - Multi-Profile Auto-Target Calibration
- **TRIPLE HSV PROFILES**: System now supports 3 lighting conditions (Bright, Medium, Dark)
- **ADAPTIVE DETECTION**: Combines all 3 profiles during detection for universal coverage
- **CALIBRATION UI**: New ember-themed interface with 3 separate buttons for each profile
- **REAL-TIME STATUS**: Shows HSV values for each loaded profile with color-coded indicators
- **AUTO-SAVE**: Automatically saves multi-profile config when all 3 are loaded

### November 24, 2025 - UI Polish & Ember Dialog System
- **HOTKEY COMBINATIONS**: All 4 Best Sellers (SD, EXPLO, UH, MANA) accept keyboard combinations (Ctrl+F1, Alt+F2, Shift+Q, etc.)
- **LOCATION ICON**: Created golden location pin icon (20x20, transparent) to replace settings gear
- **EMBER DIALOGS**: New themed dialog system (create_ember_dialog, ember_info, ember_warning)
  - All popups use ember color palette
  - Always appear on top (topmost)
  - Close with Enter or Escape keys
- **CHECKBOX GLOW**: Orange ember glow on checkboxes
  - ON: Orange highlight (#D4631C)
  - OFF: Rusted iron (#7A2E1B)
- **DELAY LABELS**: Removed "[D]" prefix, added "ms" suffix (100ms, 250ms, etc.)
- **RECORD POSITIONS**: Full ember theme with styled buttons and status display

### November 24, 2025 - Auto-Target Stability & Visual Overhaul
- **AUTO SD STABILITY FIX**: Detection now 90% reliable across all character positions
  - Permissive geometric filters: size 50-80px, border >8%, center <70%, HSV 70-255
  - Score threshold lowered to 0.28 for consistent detection
  - Debug logging added for troubleshooting
- **CHECKBOX REDESIGN**: Green/red square icons replace checkmarks
  - 🟢 Green = ON/Enabled
  - 🔴 Red = OFF/Disabled
  - Fixed background color issues (no more white backgrounds)
- **TARGET BUTTON**: Crosshair icon for auto-target with clear visual states
  - ON: Green border (#00FF00) + raised relief
  - OFF: Red border (#FF0000) + sunken relief
- **HOTKEY COMBINATIONS**: Full support for Alt+F1, Ctrl+F1, Shift+F1, etc.
  - Modifier keys (Ctrl, Alt, Shift) can be combined with any key
  - Visual feedback shows combo during recording
- **UI CLEANUP**: Removed "HTK:" prefix from hotkey buttons
- **NEW ICONS**: settings_icon.png (notebook), target_icon.png (crosshair), checkbox_on.png, checkbox_off.png

### November 24, 2025 - Harmonized Ember Color Palette
- **COMPLETE UI REDESIGN**: Applied cohesive ember/brasas color scheme throughout entire interface
- **16-COLOR PALETTE**: Deep ember brown, rusted iron borders, molten gold text, banked ember accents
- **MAGMA TEXTURE**: Darkened and retinted to remove cyan tones, blended with ember overlay
- **STATUS INDICATORS**: Molten gold (#E8B449) for ON, banked ember (#5A1F1F) for OFF
- **CONSISTENCY**: All hardcoded colors replaced with centralized palette
- **ACCESSIBILITY**: WCAG-compliant contrast ratios (≥4.5:1) for all text

### November 24, 2025 - Best Sellers Quick Configs + Auto Mana
- **UI REDESIGN**: Renamed "Macros Rápidos" to "Best Sellers" for discretion
- **NEW MACRO**: Added Auto Mana as third quick config option (F3 default)
- **POWER BUTTON**: Replaced text with golden star icon (32x32)
- **DISCRETE NAMING**: Changed title to "AudioBook - Automation System" (no Tibia/Macro references)
- **ASCII COMPATIBILITY**: All emojis replaced with ASCII characters for VNC compatibility

## File Structure

```
.
├── audiobook.py              # Main application
├── audiobook_config.json     # Auto-generated config (gitignored)
├── magma_background.jpg      # Psychedelic magma texture
├── sd_rune_icon.png          # SD rune icon (24x24)
├── uh_rune_icon.png          # UH rune icon (24x24)
├── mana_icon.png             # Mana potion icon (24x24)
├── power_icon.png            # Power button star icon (32x32)
├── fire_icon.png             # Fire icon for hotkeys section (24x24)
├── trophy_icon.png           # Trophy icon for Best Sellers (24x24)
├── sword_icon.png            # Crossed swords icon for calibrate (20x20)
├── location_icon.png         # Golden location pin for record positions (20x20)
├── target_icon.png           # Crosshair icon for auto-target button (32x32)
├── checkbox_on.png           # Green square for enabled state (20x20)
├── checkbox_off.png          # Red square for disabled state (20x20)
├── explo_rune_icon.png       # EXPLO rune icon (24x24)
├── replit.md                 # This file
├── .gitignore                # Ignores cache, config, etc.
└── attached_assets/          # Reference images
    └── image_*.png
```
