"""Tests for the English language model: scoring, segmentation, punctuation."""

import unittest

from enigma.english import (
    DEFAULT_MODEL,
    EnglishModel,
    restore_punctuation,
    restore_spaces,
    restore_text,
    score_text,
)

ENGLISH = "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG"
NOISE = "XQMZJKBVPRGLDHFTSZCWN"


class ModelTests(unittest.TestCase):
    def test_english_scores_better_than_noise(self):
        self.assertGreater(score_text(ENGLISH), score_text(NOISE))

    def test_common_words_are_known(self):
        for word in ("THE", "QUICK", "BROWN", "FOX", "ATTACK", "DAWN"):
            self.assertTrue(DEFAULT_MODEL.is_word(word))

    def test_unknown_words_are_not_known(self):
        self.assertFalse(DEFAULT_MODEL.is_word("XQZJKB"))

    def test_the_model_is_built_from_the_tables(self):
        model = EnglishModel()
        self.assertGreater(len(model.quadgram_table), 1000)
        self.assertLess(model.quadgram_floor, -5.0)

    def test_word_coverage_of_english_is_high(self):
        self.assertGreater(DEFAULT_MODEL.word_coverage(ENGLISH), 0.9)

    def test_the_model_knows_the_prepared_form(self):
        """The space markers have to look normal to the model.

        A model that only knows plain English would consider the "X" of the
        message preparation a rare letter and would rather have a wrong
        decryption without the markers.
        """
        prepared = score_text("THEXQUICKXBROWNXFOX")
        swapped = score_text("THEEQUICKEBROWNEFOE")
        self.assertGreater(prepared, swapped)

    def test_the_prepared_form_beats_random_letters(self):
        self.assertGreater(score_text("THEXQUICKXBROWNXFOX"), score_text(NOISE))


class SegmentationTests(unittest.TestCase):
    def test_segmentation_finds_the_words(self):
        tokens = DEFAULT_MODEL.segment("THEQUICKBROWNFOX")
        self.assertEqual("".join(tokens), "THEQUICKBROWNFOX")
        self.assertIn("QUICK", tokens)

    def test_the_space_marker_is_used(self):
        self.assertEqual(
            DEFAULT_MODEL.restore_spaces("THEXQUICKXBROWNXFOX"), "THE QUICK BROWN FOX"
        )

    def test_a_text_without_markers_is_segmented(self):
        self.assertEqual(
            DEFAULT_MODEL.restore_spaces("ATTACKATDAWN"), "ATTACK AT DAWN"
        )

    def test_the_q_marker_is_used_as_well(self):
        self.assertEqual(
            DEFAULT_MODEL.restore_spaces("THEQQUICKQBROWNQFOX"), "THE QUICK BROWN FOX"
        )

    def test_an_empty_text_stays_empty(self):
        self.assertEqual(DEFAULT_MODEL.restore_spaces(""), "")

    def test_only_letters_are_used(self):
        self.assertEqual(
            DEFAULT_MODEL.restore_spaces("ATTACK AT DAWN"), "ATTACK AT DAWN"
        )


class PunctuationTests(unittest.TestCase):
    def test_a_period_is_added_at_the_end(self):
        self.assertTrue(restore_punctuation("THE QUICK BROWN FOX").endswith("."))

    def test_the_first_letter_is_capitalised(self):
        self.assertTrue(restore_punctuation("hello there").startswith("Hello"))

    def test_the_standalone_i_stays_capitalised(self):
        self.assertIn("I", restore_punctuation("you and i"))
        self.assertIn("I", restore_punctuation("i am here"))

    def test_restore_text_does_both(self):
        text = restore_text("THEXQUICKXBROWNXFOX")
        self.assertIn("QUICK", text)
        self.assertTrue(text.endswith("."))


if __name__ == "__main__":
    unittest.main()
