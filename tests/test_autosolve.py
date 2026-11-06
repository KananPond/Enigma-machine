"""Tests for the automatic recovery: known key, crib attack, ciphertext only.

The attacks are slow by nature, so the messages here are short and the
searches are kept to the rotor orders they need.
"""

import unittest

from enigma import autosolve
from enigma.keys import Key
from enigma.preparation import prepare_text
from enigma.samples import SAMPLES, get, listing

HAS_NUMPY = autosolve.has_numpy()

PLAIN = (
    "THE WEATHER REPORT FOR THE CHANNEL AREA IS EXPECTED TO REMAIN CLEAR "
    "WITH LIGHT WINDS FROM THE NORTH WEST AND GOOD VISIBILITY"
)


def encrypt(plain: str, key: Key) -> str:
    return key.machine().encrypt(prepare_text(plain).text)


class CribTestCase(unittest.TestCase):
    def test_crib_with_spaces_is_read_as_separator_letters(self):
        self.assertEqual(autosolve.crib_letters("ATTACK AT DAWN"), "ATTACKXATXDAWN")
        self.assertEqual(autosolve.crib_letters("a b"), "AXB")

    def test_menu_attack_recovers_the_whole_key(self):
        key = Key(
            rotors=("I", "II", "III"),
            reflector="B",
            rings="AAA",
            positions="AAA",
            plugboard="AV BS CG",
        )
        cipher = encrypt("ATTACK AT DAWN", key)
        result = autosolve.break_with_crib(
            cipher,
            "ATTACK AT DAWN",
            offset=0,
            rotors=("I", "II", "III"),
            reflectors=("B",),
        )
        self.assertIsNotNone(result.key)
        self.assertEqual(result.key.rotors, key.rotors)
        self.assertEqual(result.key.positions, key.positions)
        self.assertEqual(result.key.reflector, key.reflector)
        self.assertIn("ATTACK AT DAWN", result.text)
        self.assertTrue(result.confident)

    def test_the_other_reading_of_the_separator_is_tried(self):
        key = Key(rotors=("II", "III", "I"), reflector="B", positions="KLM")
        cipher = encrypt("WEATHER REPORT FOR THE AREA", key)
        # the message uses Q for the spaces; the crib is written with X
        result = autosolve.break_with_crib(
            cipher,
            "WEATHERXREPORT",
            offset=0,
            rotors=("I", "II", "III"),
            reflectors=("B",),
            deadline=90,
        )
        self.assertIsNotNone(result.key)
        self.assertEqual(result.key.positions, "KLM")

    def test_a_crib_that_does_not_fit_finds_nothing(self):
        key = Key(rotors=("I", "II", "III"), reflector="B", positions="AAA")
        cipher = encrypt("ATTACK AT DAWN", key)
        result = autosolve.break_with_crib(
            cipher,
            "SUBMARINE",
            offset=0,
            rotors=("I", "II", "III"),
            reflectors=("B",),
            deadline=20,
        )
        # A crib that does not belong to the message can still be made to fit
        # a very short message; the result is then reported as doubtful
        # rather than as a key.
        self.assertFalse(result.confident)

    def test_too_short_a_crib_is_refused(self):
        result = autosolve.break_with_crib("AAAAAAAAAAAA", "AB")
        self.assertIn("太短", result.note)


class KnownKeyTestCase(unittest.TestCase):
    def test_decoding_restores_words_and_punctuation(self):
        key = Key(rotors=("III", "I", "II"), reflector="B", positions="QWE")
        cipher = encrypt("ATTACK AT DAWN", key)
        result = autosolve.decipher_with_key(cipher, key)
        self.assertEqual(result.letters, "ATTACKXATXDAWN")
        self.assertIn("ATTACK", result.text)
        self.assertEqual(result.method, "key")

    def test_the_plugboard_can_be_searched(self):
        key = Key(
            rotors=("II", "IV", "I"),
            reflector="B",
            positions="BMU",
            plugboard="AT BL DF GJ HM",
        )
        cipher = encrypt(PLAIN, key)
        blind = key.with_(plugboard="")
        result = autosolve.decipher_with_key(cipher, blind, solve=True)
        self.assertGreater(result.score, -6.0)
        self.assertIn("WEATHER", result.letters)


class CiphertextOnlyTestCase(unittest.TestCase):
    def setUp(self):
        if not HAS_NUMPY:
            self.skipTest("numpy is not installed")

    def test_a_message_without_cables_is_recovered(self):
        key = Key(rotors=("III", "I", "II"), reflector="B", positions="QWE")
        cipher = encrypt(PLAIN, key)
        result = autosolve.break_ciphertext(cipher, rotors=("I", "II", "III"))
        self.assertTrue(result.confident)
        self.assertEqual(result.key.rotors, key.rotors)
        self.assertEqual(result.key.positions, key.positions)
        self.assertIn("WEATHER REPORT", result.text)

    def test_a_fully_plugged_message_is_reported_as_hopeless(self):
        key = Key(
            rotors=("IV", "II", "V"),
            reflector="B",
            positions="ADU",
            plugboard="AV BS CG DL FU HZ IN KM OW RX",
        )
        cipher = encrypt(PLAIN, key)
        result = autosolve.break_ciphertext(cipher, rotors=("I", "II", "III"))
        self.assertFalse(result.confident)
        self.assertIn("已知明文", result.note)

    def test_a_short_message_is_refused(self):
        result = autosolve.break_ciphertext("ABCDEFGH")
        self.assertIn("太短", result.note)


class DispatchTestCase(unittest.TestCase):
    def test_a_crib_routes_to_the_menu_attack(self):
        key = Key(rotors=("I", "II", "III"), reflector="B")
        cipher = encrypt("ATTACK AT DAWN", key)
        result = autosolve.auto_decrypt(
            cipher, crib="ATTACK AT DAWN", offset=0, rotors=("I", "II", "III")
        )
        self.assertEqual(result.method, "crib")

    def test_no_crib_routes_to_the_sweep(self):
        key = Key(rotors=("I", "II", "III"), reflector="B")
        cipher = encrypt(PLAIN, key)
        result = autosolve.auto_decrypt(cipher, rotors=("I", "II", "III"))
        self.assertEqual(result.method, "ciphertext")


class SampleTestCase(unittest.TestCase):
    def test_samples_are_consistent(self):
        for sample in SAMPLES:
            prepared = prepare_text(sample.plaintext).text
            self.assertEqual(sample.key.machine().encrypt(prepared), sample.ciphertext)
            if sample.crib:
                self.assertEqual(
                    prepared[sample.crib_offset : sample.crib_offset + len(sample.crib)],
                    sample.crib,
                    sample.id,
                )

    def test_listing_and_lookup(self):
        self.assertTrue(listing())
        first = listing()[0]
        self.assertIn("title", first)
        self.assertIsNotNone(get(first["id"]))
        self.assertIsNone(get("nope"))


if __name__ == "__main__":
    unittest.main()
