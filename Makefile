PREFIX ?= /usr/local
SYSTEMD_USER_DIR = /usr/lib/systemd/user
UDEV_DIR = /etc/udev/rules.d

all:
	@echo "Nothing to build. Use 'sudo make install' to deploy system integrations."

install: install-udev install-systemd

install-udev:
	install -d $(UDEV_DIR)
	install -m 644 system/99-yyr4.rules $(UDEV_DIR)/99-yyr4.rules
	udevadm control --reload-rules || true
	udevadm trigger --subsystem-match=input || true

install-systemd:
	install -d $(SYSTEMD_USER_DIR)
	install -m 644 system/yyr4d.service $(SYSTEMD_USER_DIR)/yyr4d.service
	systemctl --user --global daemon-reload || true

uninstall:
	rm -f $(UDEV_DIR)/99-yyr4.rules
	udevadm control --reload-rules || true
	rm -f $(SYSTEMD_USER_DIR)/yyr4d.service
	systemctl --user --global daemon-reload || true
