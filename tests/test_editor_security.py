"""Tests for editor security: headers, origin, host, token, size."""

import unittest, json
from yyr4_linux_control.configurator.web.security import (
    SECURITY_HEADERS, MAX_BODY_SIZE, ALLOWED_METHODS,
    validate_origin, validate_host, validate_content_type,
    safe_path, error_json, make_error,
)


class TestSecurityHeaders(unittest.TestCase):
    def test_csp_present(self):
        self.assertIn("Content-Security-Policy", SECURITY_HEADERS)
        csp = SECURITY_HEADERS["Content-Security-Policy"]
        self.assertIn("default-src 'self'", csp)
        self.assertIn("script-src 'self'", csp)
        self.assertNotIn("unsafe-eval", csp)

    def test_nosniff(self):
        self.assertEqual(SECURITY_HEADERS["X-Content-Type-Options"], "nosniff")

    def test_no_referrer(self):
        self.assertEqual(SECURITY_HEADERS["Referrer-Policy"], "no-referrer")

    def test_no_store(self):
        self.assertIn("no-store", SECURITY_HEADERS["Cache-Control"])

    def test_frame_deny(self):
        self.assertEqual(SECURITY_HEADERS["X-Frame-Options"], "DENY")

    def test_no_external_cdn(self):
        csp = SECURITY_HEADERS["Content-Security-Policy"]
        self.assertNotIn("http:", csp)
        self.assertNotIn("https:", csp)


class TestOriginValidation(unittest.TestCase):
    def test_loopback_ok(self):
        ok, _ = validate_origin("http://127.0.0.1:9999", "127.0.0.1", 9999)
        self.assertTrue(ok)

    def test_localhost_ok(self):
        ok, _ = validate_origin("http://localhost:8080", "127.0.0.1", 8080)
        self.assertTrue(ok)

    def test_bad_origin_rejected(self):
        ok, _ = validate_origin("http://evil.com:80", "127.0.0.1", 1234)
        self.assertFalse(ok)

    def test_null_origin_ok(self):
        ok, _ = validate_origin(None, "127.0.0.1", 1234)
        self.assertTrue(ok)


class TestHostValidation(unittest.TestCase):
    def test_loopback_host_ok(self):
        ok, _ = validate_host("127.0.0.1:4321")
        self.assertTrue(ok)

    def test_loopback_no_port_ok(self):
        ok, _ = validate_host("127.0.0.1")
        self.assertTrue(ok)

    def test_bad_host_rejected(self):
        ok, _ = validate_host("0.0.0.0:8080")
        self.assertFalse(ok)

    def test_null_host_ok(self):
        ok, _ = validate_host(None)
        self.assertTrue(ok)


class TestContentTypeValidation(unittest.TestCase):
    def test_json_ok(self):
        ok, _ = validate_content_type("application/json", "POST")
        self.assertTrue(ok)

    def test_json_charset_ok(self):
        ok, _ = validate_content_type("application/json; charset=utf-8", "POST")
        self.assertTrue(ok)

    def test_non_json_rejected(self):
        ok, _ = validate_content_type("text/plain", "POST")
        self.assertFalse(ok)

    def test_null_post_rejected(self):
        ok, _ = validate_content_type(None, "POST")
        self.assertFalse(ok)

    def test_get_no_check(self):
        ok, _ = validate_content_type("text/plain", "GET")
        self.assertTrue(ok)


class TestPathSafety(unittest.TestCase):
    def test_normal_component(self):
        self.assertTrue(safe_path("editor.css"))

    def test_parent_traversal(self):
        self.assertFalse(safe_path("../etc/passwd"))

    def test_encoded_traversal(self):
        self.assertFalse(safe_path("..%2fetc%2fpasswd"))


class TestPathSafetyExtended(unittest.TestCase):
    def test_double_encoded_traversal(self):
        self.assertFalse(safe_path("%252e%252e%252f"))

    def test_backslash_traversal(self):
        self.assertFalse(safe_path("..\\etc"))

    def test_absolute_path_rejected(self):
        self.assertFalse(safe_path("/etc/passwd"))

    def test_empty_rejected(self):
        self.assertFalse(safe_path(""))

    def test_normal_asset_ok(self):
        self.assertTrue(safe_path("editor.css"))
        self.assertTrue(safe_path("editor.js"))

    def test_unknown_asset_name_ok(self):
        self.assertTrue(safe_path("some-file.data"))

    def test_percent_backslash(self):
        self.assertFalse(safe_path("%5c"))


class TestCSP(unittest.TestCase):
    def test_csp_present(self):
        from yyr4_linux_control.configurator.web.security import STRICT_CSP, SECURITY_HEADERS
        self.assertIn("Content-Security-Policy", SECURITY_HEADERS)

    def test_script_self(self):
        from yyr4_linux_control.configurator.web.security import STRICT_CSP
        self.assertIn("script-src 'self'", STRICT_CSP)

    def test_style_self(self):
        from yyr4_linux_control.configurator.web.security import STRICT_CSP
        self.assertIn("style-src 'self'", STRICT_CSP)

    def test_object_none(self):
        from yyr4_linux_control.configurator.web.security import STRICT_CSP
        self.assertIn("object-src 'none'", STRICT_CSP)

    def test_frame_ancestors_none(self):
        from yyr4_linux_control.configurator.web.security import STRICT_CSP
        self.assertIn("frame-ancestors 'none'", STRICT_CSP)

    def test_base_uri_none(self):
        from yyr4_linux_control.configurator.web.security import STRICT_CSP
        self.assertIn("base-uri 'none'", STRICT_CSP)

    def test_no_unsafe_inline(self):
        from yyr4_linux_control.configurator.web.security import STRICT_CSP
        self.assertNotIn("unsafe-inline", STRICT_CSP)

    def test_no_unsafe_eval(self):
        from yyr4_linux_control.configurator.web.security import STRICT_CSP
        self.assertNotIn("unsafe-eval", STRICT_CSP)

    def test_font_none(self):
        from yyr4_linux_control.configurator.web.security import STRICT_CSP
        self.assertIn("font-src 'none'", STRICT_CSP)

    def test_frame_src_none(self):
        from yyr4_linux_control.configurator.web.security import STRICT_CSP
        self.assertIn("frame-src 'none'", STRICT_CSP)


class TestAssetWhitelist(unittest.TestCase):
    def test_css_allowed(self):
        from yyr4_linux_control.configurator.web.security import is_allowed_asset
        self.assertTrue(is_allowed_asset("editor.css"))

    def test_js_allowed(self):
        from yyr4_linux_control.configurator.web.security import is_allowed_asset
        self.assertTrue(is_allowed_asset("editor.js"))

    def test_unknown_rejected(self):
        from yyr4_linux_control.configurator.web.security import is_allowed_asset
        self.assertFalse(is_allowed_asset("evil.js"))


class TestErrorFormatting(unittest.TestCase):
    def test_make_error(self):
        err = make_error("unauthorized", "No access")
        self.assertEqual(err["error"]["code"], "unauthorized")
        self.assertEqual(err["error"]["message"], "No access")

    def test_error_json(self):
        j = error_json("invalid_json")
        d = json.loads(j)
        self.assertEqual(d["error"]["code"], "invalid_json")

    def test_error_with_path(self):
        err = make_error("validation_error", "Bad value", path="profiles.x")
        self.assertEqual(err["error"]["path"], "profiles.x")


class TestBodySizeLimit(unittest.TestCase):
    def test_max_body_size(self):
        self.assertEqual(MAX_BODY_SIZE, 256 * 1024)


class TestAllowedMethods(unittest.TestCase):
    def test_get_allowed(self):
        self.assertIn("GET", ALLOWED_METHODS)

    def test_post_allowed(self):
        self.assertIn("POST", ALLOWED_METHODS)

    def test_delete_not_allowed(self):
        self.assertNotIn("DELETE", ALLOWED_METHODS)

    def test_put_not_allowed(self):
        self.assertNotIn("PUT", ALLOWED_METHODS)


if __name__ == "__main__":
    unittest.main()
