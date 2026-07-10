# Professional Use Cases

This document outlines 14 professional scenarios. *Disclaimer: These are proposed templates. Actual shortcuts must be verified by the user.*

## 1. Linux Desktop
* **Goal**: System navigation and media control.
* **Auto-Switch**: Default fallback.
* **K01-K12**: Media Play/Pause, Mute, App Launcher, Workspace selection.
* **E01-E04**: Master Volume, Alt-Tab, Scroll, Workspace Switcher.
* **Risks**: Accidental workspace switching.

## 2. Coding (VS Code / JetBrains / Vim)
* **Goal**: Fast editing and debugging.
* **Auto-Switch**: `WM_CLASS` = `code` or `jetbrains-*`.
* **K01-K12**: Go to Definition, Find References, Format, Run Tests, Toggle Terminal.
* **E01-E04**: Tab switching, Next Error, Vertical scroll, Code folding.
* **Fallback**: Standard arrow keys if encoder click is unverified.

## 3. Vibe Coding
* **Goal**: Safe agent interaction (AGY, Gemini CLI, Claude).
* **Layers**: Navigate, Agent, Build/Test, Review, Operations.
* **K01-K12**: Trigger prompt, View diff, Accept (Level B), Reject.
* **E01-E04**: Scroll diffs, cycle options.
* **Risks**: Auto-approving dangerous commands (Level D).

## 4. Sysadmin
* **Goal**: Managing services, journals.
* **K01-K12**: SSH launch, `systemctl restart`, `journalctl` tail.
* **E01-E04**: Scroll logs.
* **Risks**: Accidental service stop (Requires long-press).

## 5. DevOps
* **Goal**: Docker, Kubernetes management.
* **K01-K12**: Pod logs, Restart deployment, Switch Kubeconfig.
* **Risks**: Deleting resources (Requires secondary confirmation).

## 6. Video Editing (Kdenlive / DaVinci Resolve)
* **Goal**: Timeline cutting.
* **K01-K12**: Ripple Delete, Mark In/Out, Play/Pause.
* **E01-E04**: Frame jog, Timeline scroll, Timeline zoom.

## 7. Graphic Design (Inkscape / Web)
* **Goal**: Vector manipulation.
* **K01-K12**: Node tool, Select tool, Group/Ungroup.
* **E01-E04**: Canvas Zoom, Rotation.

## 8. Digital Painting (Krita)
* **Goal**: Brush control.
* **K01-K12**: Brush, Eraser, Eyedropper, Undo/Redo.
* **E01-E04**: Brush Size, Opacity, Zoom, Rotate.

## 9. Photo Editing (Darktable / GIMP)
* **Goal**: Parameter tuning.
* **K01-K12**: Next/Prev Photo, Flag, Export.
* **E01-E04**: Exposure, Contrast, Zoom.

## 10. Audio Editing (Audacity)
* **Goal**: Waveform slicing.
* **K01-K12**: Split, Silence, Play.
* **E01-E04**: Zoom, Pan, Track height.

## 11. Music Production (Ardour / DAW)
* **Goal**: Transport and mixing.
* **Note**: **[Unverified]** Native MIDI is pending. Fallback: Linux virtual MIDI ports.
* **E01-E04**: Master gain, Track pan.

## 12. Browser
* **Goal**: Tab navigation and reading.
* **K01-K12**: Back/Forward, Refresh, Bookmark.
* **E01-E04**: Tab switch, Page scroll.

## 13. Office
* **Goal**: Document and sheet formatting.
* **K01-K12**: Bold, Center, Insert row.

## 14. Communications
* **Goal**: Meeting controls.
* **K01-K12**: Push-to-talk, Camera toggle, Raise hand.
* **Risks**: Accidental unmute.
