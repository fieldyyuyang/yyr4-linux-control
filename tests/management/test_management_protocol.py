import unittest
import json
from yyr4_linux_control.management.protocol import (
    parse_request, serialize_response, ProtocolRequest, ProtocolResponse, ProtocolError
)

class TestManagementProtocol(unittest.TestCase):
    def test_parse_valid(self):
        line = '{"protocol_version": 1, "request_id": "abc", "command": "status", "params": {}}'
        req = parse_request(line)
        self.assertEqual(req.protocol_version, 1)
        self.assertEqual(req.request_id, "abc")
        self.assertEqual(req.command, "status")
        self.assertEqual(req.params, {})

    def test_parse_invalid_json(self):
        with self.assertRaises(ProtocolError) as e:
            parse_request("{not json}")
        self.assertEqual(e.exception.code, "INVALID_JSON")

    def test_parse_non_object(self):
        with self.assertRaises(ProtocolError) as e:
            parse_request("[]")
        self.assertEqual(e.exception.code, "INVALID_FORMAT")

    def test_parse_missing_version(self):
        with self.assertRaises(ProtocolError) as e:
            parse_request('{"request_id": "abc", "command": "status"}')
        self.assertEqual(e.exception.code, "MISSING_VERSION")

    def test_parse_unsupported_version(self):
        with self.assertRaises(ProtocolError) as e:
            parse_request('{"protocol_version": 2, "request_id": "abc", "command": "status"}')
        self.assertEqual(e.exception.code, "UNSUPPORTED_VERSION")

    def test_parse_missing_id(self):
        with self.assertRaises(ProtocolError) as e:
            parse_request('{"protocol_version": 1, "command": "status"}')
        self.assertEqual(e.exception.code, "INVALID_REQUEST_ID")

    def test_parse_missing_command(self):
        with self.assertRaises(ProtocolError) as e:
            parse_request('{"protocol_version": 1, "request_id": "abc"}')
        self.assertEqual(e.exception.code, "INVALID_COMMAND")

    def test_parse_unknown_fields(self):
        with self.assertRaises(ProtocolError) as e:
            parse_request('{"protocol_version": 1, "request_id": "abc", "command": "status", "extra": 1}')
        self.assertEqual(e.exception.code, "UNKNOWN_FIELDS")

    def test_serialize_success(self):
        resp = ProtocolResponse(protocol_version=1, request_id="abc", ok=True, result={"a": 1})
        line = serialize_response(resp)
        data = json.loads(line)
        self.assertEqual(data["ok"], True)
        self.assertEqual(data["result"]["a"], 1)

    def test_serialize_error(self):
        resp = ProtocolResponse(protocol_version=1, request_id="abc", ok=False, error={"code": "ERR", "message": "msg"})
        line = serialize_response(resp)
        data = json.loads(line)
        self.assertEqual(data["ok"], False)
        self.assertEqual(data["error"]["code"], "ERR")
