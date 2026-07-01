import unittest

from app.services.device_detection import parse_browser_device


class DeviceDetectionTest(unittest.TestCase):
    def test_detects_server_before_mobile_markers(self) -> None:
        ua = "H2H_PCI Android Apache-HttpClient/4.5"
        device = parse_browser_device(ua)
        self.assertEqual(device.os, "Server/H2H")
        self.assertEqual(device.model, "")

    def test_detects_iphone_models(self) -> None:
        iphone_16 = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X; iPhone17,3) "
            "AppleWebKit/605.1.15"
        )
        iphone_15_pro = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X; iPhone16,1) "
            "AppleWebKit/605.1.15"
        )
        iphone_14 = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X; iPhone15,4) "
            "AppleWebKit/605.1.15"
        )
        self.assertEqual(parse_browser_device(iphone_16).os, "iOS")
        self.assertEqual(parse_browser_device(iphone_16).model, "iPhone 16")
        self.assertEqual(parse_browser_device(iphone_15_pro).model, "iPhone 15 Pro")
        self.assertEqual(parse_browser_device(iphone_14).model, "iPhone 15")

    def test_detects_ipad_model_when_known(self) -> None:
        ipad = "Mozilla/5.0 (iPad; CPU OS 16_2 like Mac OS X; iPad13,1)"
        device = parse_browser_device(ipad)
        self.assertEqual(device.os, "iOS")
        self.assertEqual(device.model, "iPad (13,1)")

    def test_ipad_without_model_is_empty(self) -> None:
        ipad = "Mozilla/5.0 (iPad; CPU OS 16_2 like Mac OS X)"
        device = parse_browser_device(ipad)
        self.assertEqual(device.os, "iOS")
        self.assertEqual(device.model, "")

    def test_detects_android_models(self) -> None:
        samsung = "Mozilla/5.0 (Linux; Android 14; SM-S921B) AppleWebKit/537.36"
        poco = "Mozilla/5.0 (Linux; Android 13; POCO X5 Pro) AppleWebKit/537.36"
        realme = "Mozilla/5.0 (Linux; Android 14; RMX3709) AppleWebKit/537.36"
        redmi_code = "Mozilla/5.0 (Linux; Android 14; 21061119DG) AppleWebKit/537.36"
        self.assertEqual(parse_browser_device(samsung).os, "Android")
        self.assertEqual(parse_browser_device(samsung).model, "Samsung SM-S921B")
        self.assertEqual(parse_browser_device(poco).os, "Android")
        self.assertEqual(parse_browser_device(poco).model, "POCO X5 Pro")
        self.assertEqual(parse_browser_device(realme).model, "Realme GT 3 240W")
        self.assertEqual(parse_browser_device(redmi_code).model, "Redmi 10")

    def test_resolves_xiaomi_internal_codes(self) -> None:
        cases = {
            "2409BRN2CY": "Redmi 14C",
            "2312FPCA6G": "POCO M6 Pro",
            "24117RN76E": "Redmi Note 14",
        }
        for code, expected in cases.items():
            ua = f"Mozilla/5.0 (Linux; Android 14; {code}) AppleWebKit/537.36"
            self.assertEqual(parse_browser_device(ua).model, expected, code)

    def test_strips_miui_suffix_before_lookup(self) -> None:
        ua = (
            "Mozilla/5.0 (Linux; Android 10; M2006C3MNG MIUI/V12.0.16.0.QCSMIXM) "
            "AppleWebKit/537.36"
        )
        self.assertEqual(parse_browser_device(ua).model, "Redmi 9C NFC")

    def test_garbage_android_models_are_empty(self) -> None:
        cases = [
            "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 Chrome/149.0.0.0 Mobile",
            "Mozilla/5.0 (Linux; Android 14; Mobile) AppleWebKit/537.36",
            "Mozilla/5.0 (Linux; Android 14; en) AppleWebKit/537.36",
            "Mozilla/5.0 (Linux; Android 16; Android 16) AppleWebKit/537.36",
            "Mozilla/5.0 (Linux; Android 13; SDK version: 31) AppleWebKit/537.36",
        ]
        for ua in cases:
            self.assertEqual(parse_browser_device(ua).model, "", ua)

    def test_android_k_has_empty_model(self) -> None:
        chrome_k = (
            "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36"
        )
        self.assertEqual(parse_browser_device(chrome_k).os, "Android")
        self.assertEqual(parse_browser_device(chrome_k).model, "")

    def test_iphone_without_hardware_id_has_empty_model(self) -> None:
        ua = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
        )
        self.assertEqual(parse_browser_device(ua).os, "iOS")
        self.assertEqual(parse_browser_device(ua).model, "")

    def test_detects_desktop_os(self) -> None:
        windows = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        macos = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5)"
        linux = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        self.assertEqual(parse_browser_device(windows).os, "Windows")
        self.assertEqual(parse_browser_device(windows).model, "")
        self.assertEqual(parse_browser_device(macos).os, "macOS")
        self.assertEqual(parse_browser_device(linux).os, "Linux")

    def test_unknown_for_empty_or_unmatched(self) -> None:
        self.assertEqual(parse_browser_device("").os, "Unknown")
        self.assertEqual(parse_browser_device("Custom Client").os, "Unknown")


if __name__ == "__main__":
    unittest.main()
