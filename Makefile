# YYR4 Linux Control Integration Makefile
#
# Provides targets for statically verifying and installing deployment assets.

DESTDIR ?=
UDEV_RULES_DIR ?= /etc/udev/rules.d
SYSTEMD_USER_DIR ?= $(HOME)/.config/systemd/user
CONFIG_DIR ?= $(HOME)/.config/yyr4
PACKAGING_DIR ?= packaging/linux

.PHONY: help verify-linux-integration install-user-unit uninstall-user-unit install-env-example install-config-example install-udev-rule uninstall-udev-rule reload-user-manager enable-user-service disable-user-service reload-udev

help:
	@echo "YYR4 Linux Control Integration Makefile"
	@echo "Available targets:"
	@echo "  help                     - Show this help"
	@echo "  verify-linux-integration - Run static validations on deployment assets"
	@echo "  install-user-unit        - Install systemd user unit to $(DESTDIR)$(SYSTEMD_USER_DIR)"
	@echo "  uninstall-user-unit      - Remove systemd user unit from $(DESTDIR)$(SYSTEMD_USER_DIR)"
	@echo "  install-env-example      - Install yyr4d.env.example to $(DESTDIR)$(CONFIG_DIR)"
	@echo "  install-config-example   - Install yyr4-control.toml to $(DESTDIR)$(CONFIG_DIR)/config.toml.example"
	@echo "  install-udev-rule        - Install udev rule to $(DESTDIR)$(UDEV_RULES_DIR) (requires sufficient permissions)"
	@echo "  uninstall-udev-rule      - Remove udev rule from $(DESTDIR)$(UDEV_RULES_DIR) (requires sufficient permissions)"
	@echo "  reload-user-manager      - Run systemctl --user daemon-reload"
	@echo "  enable-user-service      - Run systemctl --user enable yyr4d.service"
	@echo "  disable-user-service     - Run systemctl --user disable yyr4d.service"
	@echo "  reload-udev              - Run udevadm control --reload-rules && udevadm trigger (requires sufficient permissions)"

verify-linux-integration:
	@echo "Running Python static asset tests..."
	env PYTHONPATH=src python3 -m unittest tests.test_linux_integration_assets

install-user-unit:
	install -d $(DESTDIR)$(SYSTEMD_USER_DIR)
	install -m 0644 $(PACKAGING_DIR)/systemd/user/yyr4d.service $(DESTDIR)$(SYSTEMD_USER_DIR)/yyr4d.service

uninstall-user-unit:
	rm -f $(DESTDIR)$(SYSTEMD_USER_DIR)/yyr4d.service

install-env-example:
	install -d $(DESTDIR)$(CONFIG_DIR)
	install -m 0600 $(PACKAGING_DIR)/yyr4d.env.example $(DESTDIR)$(CONFIG_DIR)/yyr4d.env.example

install-config-example:
	install -d $(DESTDIR)$(CONFIG_DIR)
	install -m 0644 examples/yyr4-control.toml $(DESTDIR)$(CONFIG_DIR)/config.toml.example

install-udev-rule:
	install -d $(DESTDIR)$(UDEV_RULES_DIR)
	install -m 0644 $(PACKAGING_DIR)/udev/99-yyr4.rules $(DESTDIR)$(UDEV_RULES_DIR)/99-yyr4.rules

uninstall-udev-rule:
	rm -f $(DESTDIR)$(UDEV_RULES_DIR)/99-yyr4.rules

reload-user-manager:
	systemctl --user daemon-reload

enable-user-service:
	systemctl --user enable yyr4d.service

disable-user-service:
	systemctl --user disable yyr4d.service

reload-udev:
	udevadm control --reload-rules
	udevadm trigger --subsystem-match=input
