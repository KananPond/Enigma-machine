"""Tests for the decoder: deciphering, restoring the text, finding the plugboard."""

import unittest

from enigma import EnigmaMachine, Plugboard
from enigma.decode import decode, decipher, solve_plugboard

TEXT = "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG"


def machine(**kwargs) -> EnigmaMachine:
    """Build a machine with the classic default settings."""
    settings = {
        "rotor_order": ("I", "II", "III"),
        "reflector": "B",
        "ring_settings": ("A", "A", "A"),
        "positions": ("A", "A", "A"),
    }
    settings.update(kwargs)
    return EnigmaMachine.create(**settings)


class DecipherTests(unittest.TestCase):
    def test_the_ciphertext_is_reversed(self):
        eng = machine()
        cipher = eng.encrypt("ATTACKATDAWN")
        letters, plugboard, positions = decipher(cipher, eng, positions="AAA")
        self.assertEqual(letters, "ATTACKATDAWN")
        self.assertEqual(positions, "AAA")
        self.assertEqual(plugboard.pair_count, 0)

    def test_the_plugboard_is_taken_into_account(self):
        eng = machine(plugboard=Plugboard.parse("AV BS"))
        cipher = eng.encrypt("ATTACKATDAWN")
        letters, plugboard, _positions = decipher(cipher, eng, positions="AAA")
        self.assertEqual(letters, "ATTACKATDAWN")
        self.assertEqual(plugboard.describe(), "AV BS")

    def test_the_starting_position_is_used(self):
        eng = machine(positions=("A", "D", "U"))
        cipher = eng.encrypt("ATTACKATDAWN")
        letters, _plugboard, positions = decipher(cipher, eng, positions="ADU")
        self.assertEqual(letters, "ATTACKATDAWN")
        self.assertEqual(positions, "ADU")

    def test_the_core_permutation_matches_the_machine(self):
        """The permutation has to agree with what a key press does."""
        eng = machine()
        twin = machine()
        for index in range(26):
            letter = chr(65 + index)
            expected = ord(twin.press(letter)) - 65
            eng.step_rotors()
            self.assertEqual(eng.core_permutation()[index], expected)

    def test_the_core_is_its_own_inverse(self):
        eng = machine()
        permutation = eng.core_permutation()
        for index in range(26):
            self.assertEqual(permutation[permutation[index]], index)


class DecodeTests(unittest.TestCase):
    def test_the_words_are_restored(self):
        eng = machine()
        prepared = TEXT.replace(" ", "X")
        cipher = eng.encrypt(prepared)
        result = decode(cipher, eng, positions="AAA")
        self.assertEqual(result.letters, prepared)
        self.assertIn("QUICK", result.words)
        self.assertIn("QUICK", result.text)

    def test_the_punctuation_is_restored(self):
        eng = machine()
        cipher = eng.encrypt(TEXT.replace(" ", "X"))
        result = decode(cipher, eng, positions="AAA")
        self.assertTrue(result.text.endswith("."))

    def test_the_spaces_can_be_switched_off(self):
        eng = machine()
        cipher = eng.encrypt("ATTACKATDAWN")
        result = decode(cipher, eng, positions="AAA", with_spaces=False)
        self.assertEqual(result.letters, "ATTACKATDAWN")
        self.assertEqual(result.words, ["ATTACKATDAWN"])

    def test_an_empty_ciphertext_is_handled(self):
        result = decode("", machine())
        self.assertEqual(result.letters, "")
        self.assertEqual(result.text, "")


class PlugboardSearchTests(unittest.TestCase):
    def test_the_plugboard_is_found(self):
        """The search has to recover a wiring it was never told about."""
        prepared = (TEXT + " ") * 3
        prepared = prepared.replace(" ", "X")
        plugged = machine(plugboard=Plugboard.parse("AV BS CG"))
        cipher = plugged.encrypt(prepared)

        result = solve_plugboard(
            cipher,
            machine(),
            positions="AAA",
            sample=200,
            beam=4,
            max_rounds=8,
        )
        self.assertEqual(result.plugboard.pair_count, 3)
        self.assertEqual(result.letters, prepared)

    def test_the_search_reports_its_progress(self):
        plugged = machine(plugboard=Plugboard.parse("AV BS"))
        cipher = plugged.encrypt(TEXT.replace(" ", "X"))
        rounds = []
        result = solve_plugboard(
            cipher,
            machine(),
            positions="AAA",
            sample=120,
            beam=3,
            max_rounds=4,
            progress=lambda round_index, _score: rounds.append(round_index),
        )
        self.assertTrue(rounds)
        self.assertGreater(result.evaluations, 0)

    def test_a_short_message_gives_no_plugboard(self):
        """Too few letters cannot tell a wiring from a coincidence."""
        eng = machine()
        result = solve_plugboard(eng.encrypt("ATTACKATDAWN"), eng, positions="AAA")
        self.assertEqual(result.plugboard.pair_count, 0)
        self.assertFalse(result.confident)

    def test_the_right_wiring_scores_better_than_a_wrong_one(self):
        """The language model has to prefer the wiring that was really used."""
        prepared = (TEXT + " ") * 3
        prepared = prepared.replace(" ", "X")
        plugged = machine(plugboard=Plugboard.parse("AV BS CG"))
        cipher = plugged.encrypt(prepared)

        right = decode(cipher, machine(), positions="AAA",
                       plugboard=Plugboard.parse("AV BS CG"))
        wrong = decode(cipher, machine(), positions="AAA",
                       plugboard=Plugboard.parse("AV BS CG EX"))
        self.assertGreater(right.score, wrong.score)
        self.assertEqual(right.letters, prepared)


if __name__ == "__main__":
    unittest.main()
