import unittest
import os
import re
from pathlib import Path

class TestLinuxIntegrationAssets(unittest.TestCase):
    def setUp(self):
        self.base_dir = Path(__file__).parent.parent
        self.udev_rule = self.base_dir / "packaging" / "linux" / "udev" / "99-yyr4.rules"
        self.systemd_unit = self.base_dir / "packaging" / "linux" / "systemd" / "user" / "yyr4d.service"
        self.makefile = self.base_dir / "Makefile"
        self.env_example = self.base_dir / "packaging" / "linux" / "yyr4d.env.example"

    def test_udev_rule(self):
        self.assertTrue(self.udev_rule.exists())
        content = self.udev_rule.read_text()
        
        # Must contain
        self.assertIn('239a', content)
        self.assertIn('80f4', content)
        self.assertIn('event*', content)
        self.assertIn('TAG+="uaccess"', content)
        
        # Must NOT contain
        self.assertNotIn('MODE="0666"', content)
        self.assertNotIn('MODE="0777"', content)
        self.assertNotIn('MODE="666"', content)
        self.assertNotIn('GROUP=', content)
        self.assertNotIn('OWNER=', content)
        self.assertNotIn('RUN+=', content)
        self.assertNotIn('PROGRAM=', content)
        self.assertNotIn('chmod', content)
        self.assertNotIn('setfacl', content)

    def test_systemd_unit(self):
        self.assertTrue(self.systemd_unit.exists())
        content = self.systemd_unit.read_text()
        
        self.assertIn('Type=simple', content)
        self.assertIn('--config', content)
        self.assertIn('--control-socket', content)
        self.assertIn('yyr4ctl validate', content)
        self.assertIn('RuntimeDirectory=yyr4', content)
        self.assertIn('RuntimeDirectoryMode=0700', content)
        self.assertIn('UMask=0077', content)
        self.assertIn('Restart=on-failure', content)
        self.assertIn('KillSignal=SIGTERM', content)
        self.assertIn('RestrictAddressFamilies=AF_UNIX', content)
        self.assertIn('NoNewPrivileges=true', content)
        
        self.assertNotIn('User=root', content)
        self.assertNotIn('sudo ', content)
        self.assertNotIn('PrivateDevices=true', content)
        self.assertNotIn('AF_INET', content)

    def test_makefile(self):
        self.assertTrue(self.makefile.exists())
        content = self.makefile.read_text()
        
        self.assertNotIn('sudo ', content)
        self.assertNotIn('rm -rf', content)
        self.assertNotIn('git ', content)
        self.assertIn('$(DESTDIR)', content)
        
        # Must not overwrite user's actual config.toml
        self.assertNotIn('$(DESTDIR)$(CONFIG_DIR)/config.toml', content.replace('config.toml.example', ''))

    def test_env_example(self):
        self.assertTrue(self.env_example.exists())
        content = self.env_example.read_text()
        
        self.assertNotIn('fieldy', content)
        self.assertNotIn('root', content)
        self.assertNotIn('token', content.lower())
        self.assertNotIn('password', content.lower())
        self.assertIn('X11', content)

if __name__ == '__main__':
    unittest.main()
