"""Tests for writing numbers out."""

import unittest

from enigma.numbers import (
    digits_to_words,
    expand_numbers,
    number_to_words,
    readable_number_words,
)


class NumberToWordsTests(unittest.TestCase):
    def test_simple_numbers(self):
        self.assertEqual(number_to_words(0), "ZERO")
        self.assertEqual(number_to_words(7), "SEVEN")
        self.assertEqual(number_to_words(13), "THIRTEEN")
        self.assertEqual(number_to_words(20), "TWENTY")
        self.assertEqual(number_to_words(42), "FORTY TWO")

    def test_readable_year(self):
        self.assertEqual(
            number_to_words(1932), "ONE THOUSAND NINE HUNDRED THIRTY TWO"
        )

    def test_year_is_read_the_british_way(self):
        self.assertEqual(readable_number_words(1932), "NINETEEN THIRTY TWO")
        self.assertEqual(readable_number_words(1944), "NINETEEN FORTY FOUR")
        self.assertEqual(readable_number_words(2001), "TWENTY OH ONE")
        self.assertEqual(readable_number_words(1900), "NINETEEN HUNDRED")

    def test_other_numbers_keep_the_quantity_reading(self):
        self.assertEqual(readable_number_words(42), "FORTY TWO")
        self.assertEqual(
            readable_number_words(123456), "ONE HUNDRED TWENTY THREE THOUSAND FOUR HUNDRED FIFTY SIX"
        )

    def test_hundreds_and_thousands(self):
        self.assertEqual(number_to_words(100), "ONE HUNDRED")
        self.assertEqual(number_to_words(101), "ONE HUNDRED ONE")
        self.assertEqual(number_to_words(1234), "ONE THOUSAND TWO HUNDRED THIRTY FOUR")
        self.assertEqual(
            number_to_words(1234567),
            "ONE MILLION TWO HUNDRED THIRTY FOUR THOUSAND FIVE HUNDRED SIXTY SEVEN",
        )

    def test_negative(self):
        self.assertEqual(number_to_words(-5), "MINUS FIVE")


class DigitsToWordsTests(unittest.TestCase):
    def test_concatenated(self):
        self.assertEqual(digits_to_words("48152"), "FOUREIGHTONEFIVETWO")
        self.assertEqual(digits_to_words("0"), "ZERO")
        self.assertEqual(digits_to_words("907"), "NINEZEROSEVEN")


class ExpandNumbersTests(unittest.TestCase):
    def test_words_policy(self):
        self.assertEqual(expand_numbers("1932", "words"), "NINETEEN THIRTY TWO")
        self.assertEqual(
            expand_numbers("in 1932 we", "words"), "in NINETEEN THIRTY TWO we"
        )

    def test_digits_policy(self):
        self.assertEqual(expand_numbers("1932", "digits"), "ONENINETHREETWO")
        self.assertEqual(expand_numbers("48152", "digits"), "FOUREIGHTONEFIVETWO")

    def test_auto_policy_uses_words_for_short_numbers(self):
        self.assertEqual(expand_numbers("1932", "auto"), "NINETEEN THIRTY TWO")
        self.assertEqual(expand_numbers("42", "auto"), "FORTY TWO")

    def test_auto_policy_keeps_long_numbers_exact(self):
        self.assertEqual(expand_numbers("48152", "auto"), "FOUREIGHTONEFIVETWO")

    def test_join_words(self):
        self.assertEqual(
            expand_numbers("1932", "words", join_words=True), "NINETEENTHIRTYTWO"
        )

    def test_thousands_separator(self):
        self.assertEqual(
            expand_numbers("1,234", "words"), "ONE THOUSAND TWO HUNDRED THIRTY FOUR"
        )

    def test_decimal(self):
        self.assertEqual(expand_numbers("3.14", "words"), "THREE POINT ONE FOUR")
        self.assertEqual(expand_numbers("3.14", "digits"), "THREEONEFOUR")

    def test_text_without_numbers_is_untouched(self):
        self.assertEqual(expand_numbers("hello world", "auto"), "hello world")

    def test_unknown_policy(self):
        with self.assertRaises(ValueError):
            expand_numbers("12", "nonsense")


if __name__ == "__main__":
    unittest.main()
