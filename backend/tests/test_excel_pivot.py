import unittest

from app.services.excel_pivot import _column_letter, native_pivot_available


class ExcelPivotHelpersTest(unittest.TestCase):
    def test_column_letter(self) -> None:
        self.assertEqual(_column_letter(1), "A")
        self.assertEqual(_column_letter(16), "P")
        self.assertEqual(_column_letter(26), "Z")
        self.assertEqual(_column_letter(27), "AA")

    def test_native_pivot_available_returns_bool(self) -> None:
        self.assertIsInstance(native_pivot_available(), bool)


if __name__ == "__main__":
    unittest.main()
