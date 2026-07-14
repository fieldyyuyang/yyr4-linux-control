# Linux Integration and Deployment

This document covers the deployment, systemd integration, and udev rules for the `yyr4d` daemon (Milestone 4).

## Architecture

`yyr4d` is designed to run as a **non-root user service**. This ensures:
1. It has access to the user's graphical session (X11/Wayland) via tools like `xdotool` or `uinput`.
2. It respects the principle of least privilege.
3. It ties the execution of the macro pad context to the active user's desktop session.

### Udev Rules
To allow the unprivileged user to read raw inputs from the YYR4 device without setting global `chmod 777` or manually adding users to the `input` group, we use `logind` ACLs.

**File:** `system/99-yyr4.rules`
```udev
ACTION=="add|change", SUBSYSTEM=="input", ATTRS{idVendor}=="239a", ATTRS{idProduct}=="80f4", TAG+="uaccess"
```
The `TAG+="uaccess"` automatically assigns read/write permissions to the user physically sitting at the active seat.

### Systemd User Unit
**File:** `system/yyr4d.service`

- Runs as a `systemd --user` service.
- Automatically falls back to `%h/.config/yyr4/config.toml` (which resolves to `~/.config/yyr4/config.toml`).
- Waits for the `graphical-session.target`.
- Configured to auto-restart on failure.
- Logs are automatically collected by `journalctl --user -u yyr4d`.

## Installation

A standard `Makefile` is provided.

```bash
# 1. Install Python package (user or system wide depending on your preference)
python3 -m pip install .

# 2. Install udev and systemd rules (requires sudo)
sudo make install
```

## Real-Host Verification Steps

To safely verify this on a real host:

1. **Test the Daemon Interactively:**
   ```bash
   # Ensure you have a valid config at ~/.config/yyr4/config.toml
   mkdir -p ~/.config/yyr4
   cp examples/yyr4-control.toml ~/.config/yyr4/config.toml
   
   # Run directly to verify permissions
   yyr4d
   ```
2. **Test Udev Rules:**
   ```bash
   sudo make install-udev
   # Unplug and replug the YYR4 keypad.
   # Check permissions:
   ls -l /dev/input/by-id/*YOUYOU*
   # You should see a '+' at the end of permissions (indicating an ACL is applied).
   getfacl /dev/input/eventX
   # Should list your username with read/write access.
   ```
3. **Test Systemd Unit:**
   ```bash
   sudo make install-systemd
   
   # Enable and start
   systemctl --user daemon-reload
   systemctl --user enable --now yyr4d
   
   # Check status
   systemctl --user status yyr4d
   
   # Verify CLI connectivity
   yyr4ctl status
   ```
4. **Test Idempotency:**
   - Running `sudo make install` multiple times does not break state.
   - `sudo make uninstall` correctly cleans up.
