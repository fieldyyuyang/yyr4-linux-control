# Linux Integration and Deployment

This document describes the deployment architecture and system integration guidelines for `yyr4-linux-control` on a modern Linux desktop.

**Note: Currently in Milestone 4, Phase A. Static deployment assets are verified, but real host installation acceptance is pending.**

## 1. Architecture Overview
YYR4 runs entirely in userspace as a normal unprivileged application. It interacts with the device's event nodes via the Linux input subsystem, translates hardware actions according to layered profiles, and optionally executes commands or desktop automation like `xdotool`.

## 2. udev & logind `uaccess` Principle
To access `/dev/input/event*` nodes without root privileges, YYR4 relies on `systemd-logind`. 
The `99-yyr4.rules` udev rule adds the `TAG+="uaccess"` to the specific YYR4 input nodes (VID 239a, PID 80f4). When a user physically logs into a local session, `logind` automatically grants that active user read/write ACLs to the tagged nodes.

## 3. Why Not `MODE="0666"`?
Using `MODE="0666"` or `0777` makes the raw keystrokes and controls globally readable and writable to any background process on the system, creating a severe security vulnerability (keylogger vector). `uaccess` correctly isolates access to the active session user.

## 4. Why Not Static `GROUP="input"`?
Adding the user to the static `input` group grants them global access to *all* keyboards and mice on the system permanently, regardless of active session status. This breaks modern seat management boundaries.

## 5. systemd User Service Model
The `yyr4d` daemon is designed to run as a **systemd user service** (`systemctl --user`), executing inside the context of the user's graphical session. It automatically inherits standard user paths, logs to the user's journal, and prevents root execution.

## 6. Python Package Prerequisites
Ensure the YYR4 Python package is installed into the user's environment (e.g. `pipx install .` or `pip install --user .`). The `yyr4d` and `yyr4ctl` commands must be available in `~/.local/bin` (or equivalent `PATH`).

## 7. User Configuration Path
Configuration must be explicitly passed to `yyr4d`. The standardized path is:
`~/.config/yyr4/config.toml`

## 8. Environment File Path
For X11 environment variables (when systemd does not automatically export them):
`~/.config/yyr4/yyr4d.env`

## 9. User Unit Path
`~/.config/systemd/user/yyr4d.service`

## 10. Udev Rules Path
`/etc/udev/rules.d/99-yyr4.rules`

## 11. Installation Commands
```bash
# Install user assets (No root needed)
make install-user-unit install-config-example install-env-example

# Install udev rules (Requires sufficient privileges, e.g. root)
sudo make install-udev-rule
```

## 12. Uninstallation Commands
```bash
# Uninstall user assets
make uninstall-user-unit

# Uninstall udev rules (Requires privileges)
sudo make uninstall-udev-rule
```

## 13. Systemd Daemon Reload
After installing or modifying the user unit:
```bash
make reload-user-manager
# or: systemctl --user daemon-reload
```

## 14. Service Management
```bash
systemctl --user enable yyr4d.service
systemctl --user start yyr4d.service
systemctl --user stop yyr4d.service
systemctl --user restart yyr4d.service
systemctl --user status yyr4d.service
```

## 15. Checking Logs
```bash
journalctl --user -u yyr4d.service -f
```

## 16. Udev Reload & Device Re-plug
After installing the udev rules, you must reload them and trigger them.
```bash
sudo make reload-udev
```
Alternatively, physically unplug and re-plug the YYR4 device for logind to assign ACLs.

## 17. Validating Configuration
`yyr4ctl validate --config ~/.config/yyr4/config.toml`
The daemon executes this automatically in `ExecStartPre` to prevent starting with a broken config.

## 18. Checking Daemon Status
`yyr4ctl status`

## 19. Checking Current Context
`yyr4ctl context`

## 20. X11 Environment
When using `CommandAction` or `HotkeyAction` that invoke `xdotool`, the process must know the X11 `DISPLAY` and `XAUTHORITY`. The `yyr4d.env` example demonstrates how to set these. Systemd user services sometimes lack GUI variables depending on the distro's startup order.

## 21. Wayland Limitations
**Wayland is strictly unsupported by the current desktop backend (XDoTool).** Attempting to inject keystrokes via `xdotool` on pure Wayland will fail with `backend unavailable`.

## 22. Configuration Security
The `~/.config/yyr4` directory and its contents should be kept private (e.g. `0700` directory, `0600` files) since configurations may execute arbitrary shell commands.

## 23. CommandAction Risks
The daemon runs in `EXECUTE` mode by default, which enables real system actions. Any `CommandAction` in your TOML will execute exactly as defined. Do not download and run unverified profiles.

## 24. Rollback Steps
If an update fails:
1. `systemctl --user stop yyr4d`
2. Revert to previous `config.toml`.
3. Re-run `pip install` for the previous package version.
4. `systemctl --user start yyr4d`.

## 25. Troubleshooting
- **Permission Denied opening `/dev/input/...`**: Did you install the udev rules? Are you logged in locally? Unplug and replug the device. Check `getfacl /dev/input/eventX`.
- **Daemon fails immediately**: Check `journalctl --user -u yyr4d`. It likely failed `ExecStartPre` due to invalid TOML.
- **Commands work but Keyboard Macros fail**: Check X11 `DISPLAY` in `yyr4d.env`.

## 26. No `sudo` for Daemon
Do not run `yyr4d` or `yyr4ctl` using `sudo`.

## 27. Root is Forbidden
`yyr4d` explicitly forbids running as `root` (uid 0) and will refuse to start to protect the system.

## 28. Real Host Acceptance Pending
The real installation on a host machine is pending.

### Milestone 4 Phase B: Real Host Acceptance Checklist
(This checklist will be executed in the next stage. Do not execute these now.)
- [ ] Install udev rules and verify file exists.
- [ ] Reload udev and physically re-plug device.
- [ ] Check `getfacl /dev/input/event*` to verify your username has ACL `rw`.
- [ ] Install systemd user unit.
- [ ] Run `systemctl --user start yyr4d`.
- [ ] Verify `yyr4ctl status` returns correctly.
- [ ] Verify `yyr4ctl context` returns current layer and profile.
- [ ] Execute a harmless binding (e.g., a simple key that types a letter, or opens a calculator).
- [ ] Run `systemctl --user restart yyr4d` and verify it recovers.
- [ ] Log out and log back into the graphical session, verify daemon autostarts successfully.
- [ ] Uninstall all integration assets and verify cleanup.
