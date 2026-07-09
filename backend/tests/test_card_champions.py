import unittest

from app.services.card_champions import mask_card_number


class CardMaskTest(unittest.TestCase):
    def test_masks_standard_pan(self) -> None:
        self.assertEqual(mask_card_number("4111111111111111"), "411111******1111")

    def test_empty_card(self) -> None:
        self.assertEqual(mask_card_number(""), "(no card)")
        self.assertEqual(mask_card_number(None), "(no card)")

    def test_short_value_is_kept(self) -> None:
        self.assertEqual(mask_card_number("123456789"), "123456789")


if __name__ == "__main__":
    unittest.main()
