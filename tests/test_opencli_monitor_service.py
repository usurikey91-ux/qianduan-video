import json
import unittest
from unittest.mock import patch

from backend_app.modules.opencli_monitor import service


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class OpenCLIAdminServiceTests(unittest.TestCase):
    def test_parses_stable_sec_uid_from_profile_url(self):
        sec_uid, profile_url = service.parse_douyin_sec_uid(
            "https://www.douyin.com/user/MS4wLjABAAAA-example?from=share"
        )
        self.assertEqual("MS4wLjABAAAA-example", sec_uid)
        self.assertEqual("https://www.douyin.com/user/MS4wLjABAAAA-example", profile_url)

    def test_rejects_profile_without_stable_id(self):
        with self.assertRaisesRegex(ValueError, "sec_uid"):
            service.parse_douyin_sec_uid("https://www.douyin.com/")

    def test_parses_generic_platform_profile_reference(self):
        external_id, profile_url = service.parse_account_reference(
            "bilibili", "https://space.bilibili.com/12345"
        )
        self.assertEqual("12345", external_id)
        self.assertEqual("https://space.bilibili.com/12345", profile_url)

    def test_generic_account_binding_sends_platform(self):
        with patch("backend_app.modules.opencli_monitor.service._request") as request:
            request.return_value = {"created": True}
            result = service.bind_account(
                "bilibili",
                "https://space.bilibili.com/12345",
                settings={"opencliAdminBaseUrl": "http://collector.test/api/v1"},
            )
        self.assertEqual({"created": True}, result)
        payload = request.call_args.kwargs["payload"]
        self.assertEqual("bilibili", payload["platform"])
        self.assertEqual("12345", payload["external_account_id"])

    @patch("backend_app.modules.opencli_monitor.service.urlopen")
    def test_bind_calls_auxiliary_service(self, mocked_urlopen):
        mocked_urlopen.return_value = _Response({"success": True, "data": {"created": True}})
        result = service.bind_douyin_account(
            "https://www.douyin.com/user/MS4wLjABAAAA-example",
            settings={"opencliAdminBaseUrl": "http://127.0.0.1:8000/api/v1"},
        )
        request = mocked_urlopen.call_args.args[0]
        self.assertEqual("POST", request.method)
        self.assertTrue(request.full_url.endswith("/integrations/sunbird/accounts"))
        self.assertEqual({"created": True}, result)

    @patch("backend_app.modules.opencli_monitor.service._request")
    def test_queue_combines_hot_and_very_hot_with_priority_first(self, request):
        request.side_effect = [
            [{"external_work_id": "hot", "relative_multiple": 4, "priority": False}],
            [{"external_work_id": "very-hot", "relative_multiple": 5, "priority": True}],
        ]
        queue = service.list_analysis_queue()
        self.assertEqual(["very-hot", "hot"], [item["external_work_id"] for item in queue])


if __name__ == "__main__":
    unittest.main()
