"""Tests for the message preparation pipeline."""

import unittest

from enigma.message import split_messages
from enigma.preparation import choose_space_letter, prepare_text


class SpaceSubstituteTests(unittest.TestCase):
    def test_x_is_used_when_q_is_rarer(self):
        self.assertEqual(choose_space_letter("Q"), "X")
        self.assertEqual(choose_space_letter("X"), "Q")

    def test_ties_go_to_x(self):
        self.assertEqual(choose_space_letter("XQ"), "X")
        self.assertEqual(choose_space_letter(""), "X")

    def test_more_x_than_q_picks_q(self):
        self.assertEqual(choose_space_letter("XXQ"), "Q")


class PrepareTextTests(unittest.TestCase):
    def test_spaces_become_the_chosen_letter(self):
        prepared = prepare_text("HELLO WORLD")
        self.assertEqual(prepared.text, "HELLOXWORLD")
        self.assertEqual(prepared.space_letter, "X")

    def test_q_is_used_when_the_text_contains_more_x(self):
        prepared = prepare_text("XX X XX")
        self.assertEqual(prepared.space_letter, "Q")
        self.assertEqual(prepared.text, "XXQXQXX")

    def test_forced_space_letter(self):
        prepared = prepare_text("HELLO WORLD", space_letter="Q")
        self.assertEqual(prepared.text, "HELLOQWORLD")
        self.assertEqual(prepared.space_letter, "Q")

    def test_invalid_space_letter(self):
        with self.assertRaises(ValueError):
            prepare_text("HELLO", space_letter="Z")

    def test_numbers_are_written_out(self):
        prepared = prepare_text("1932", number_policy="words")
        # the words of the number keep their spaces, which become the
        # space substitute just like the spaces of the text
        self.assertEqual(prepared.text, "NINETEENXTHIRTYXTWO")
        self.assertEqual(prepared.expanded, "NINETEEN THIRTY TWO")
        self.assertEqual(prepared.space_letter, "X")

    def test_exact_numbers_are_spelled_digit_by_digit(self):
        prepared = prepare_text("48152", number_policy="digits")
        self.assertEqual(prepared.text, "FOUREIGHTONEFIVETWO")

    def test_joined_number_words(self):
        prepared = prepare_text("1932", number_policy="words", join_number_words=True)
        self.assertEqual(prepared.text, "NINETEENTHIRTYTWO")

    def test_punctuation_is_dropped(self):
        prepared = prepare_text("ATTACK, AT DAWN!")
        self.assertEqual(prepared.text, "ATTACKXATXDAWN")
        self.assertGreater(prepared.letters_removed, 0)

    def test_letters_only_output(self):
        prepared = prepare_text("a1b2c3")
        self.assertTrue(prepared.text.isalpha())

    def test_expanded_text_is_available(self):
        prepared = prepare_text("1932", number_policy="words")
        self.assertEqual(prepared.expanded, "NINETEEN THIRTY TWO")


class SplitMessagesTests(unittest.TestCase):
    def test_splits_on_blank_lines(self):
        text = "FIRST MESSAGE\nSECOND LINE\n\n\nNEXT MESSAGE"
        self.assertEqual(
            split_messages(text), ["FIRST MESSAGE\nSECOND LINE", "NEXT MESSAGE"]
        )

    def test_single_message(self):
        self.assertEqual(split_messages("just one"), ["just one"])

    def test_empty_text(self):
        self.assertEqual(split_messages(""), [])
        self.assertEqual(split_messages("   \n\n "), [])


if __name__ == "__main__":
    unittest.main()
