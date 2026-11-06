"""Tests for the key sheet - reading, validating and normalising settings."""

import unittest

from enigma.keys import Key, KeyError_, MAX_CABLES


class KeyTestCase(unittest.TestCase):
    def test_defaults(self):
        key = Key()
        self.assertEqual(key.rotors, ("I", "II", "III"))
        self.assertEqual(key.reflector, "B")
        self.assertEqual(key.rings, "AAA")
        self.assertEqual(key.positions, "AAA")
        self.assertEqual(key.plugboard, "")

    def test_reads_a_full_sheet(self):
        key = Key.from_dict(
            {
                "rotors": ["IV", "II", "V"],
                "reflector": "C",
                "rings": "BUL",
                "positions": "ADU",
                "plugboard": "AV BS CG",
            }
        )
        self.assertEqual(key.rotors, ("IV", "II", "V"))
        self.assertEqual(key.reflector, "C")
        self.assertEqual(key.rings, "BUL")
        self.assertEqual(key.positions, "ADU")
        self.assertEqual(key.plugboard, "AV BS CG")
        self.assertEqual(key.cable_count, 3)

    def test_rotors_can_be_written_as_one_string(self):
        key = Key.from_dict({"rotors": "I-IV-VII"})
        self.assertEqual(key.rotors, ("I", "IV", "VII"))

    def test_plugboard_is_canonical(self):
        key = Key.from_dict({"plugboard": "va bs"})
        self.assertEqual(key.plugboard, "AV BS")

    def test_lower_case_is_accepted(self):
        key = Key.from_dict({"positions": "adu", "rings": "bul"})
        self.assertEqual(key.positions, "ADU")
        self.assertEqual(key.rings, "BUL")

    def test_a_rotor_cannot_be_fitted_twice(self):
        with self.assertRaises(KeyError_):
            Key(rotors=("I", "I", "III"))

    def test_unknown_rotor_is_rejected(self):
        with self.assertRaises(KeyError_):
            Key(rotors=("I", "IX", "III"))

    def test_unknown_reflector_is_rejected(self):
        with self.assertRaises(KeyError_):
            Key(reflector="Q")

    def test_short_positions_are_rejected(self):
        with self.assertRaises(KeyError_):
            Key(positions="AB")

    def test_odd_plugboard_is_rejected(self):
        with self.assertRaises(KeyError_):
            Key(plugboard="AV B")

    def test_a_letter_cannot_be_used_twice(self):
        with self.assertRaises(KeyError_):
            Key(plugboard="AV AB")

    def test_a_letter_cannot_be_plugged_into_itself(self):
        with self.assertRaises(KeyError_):
            Key(plugboard="AA")

    def test_too_many_cables_are_rejected(self):
        with self.assertRaises(KeyError_):
            Key(plugboard="AB CD EF GH IJ KL MN OP QR ST UV")

    def test_maximum_number_of_cables_is_accepted(self):
        key = Key(plugboard="AB CD EF GH IJ KL MN OP QR ST")
        self.assertEqual(key.cable_count, MAX_CABLES)

    def test_machine_is_built_from_the_key(self):
        key = Key.from_dict({"plugins": "AV"})
        machine = key.machine()
        self.assertEqual(machine.positions, "AAA")
        self.assertEqual(machine.plugboard.describe(), "")

        machine = key.with_(plugboard="AV BS").machine()
        self.assertEqual(machine.plugboard.describe(), "AV BS")

    def test_machine_can_start_elsewhere(self):
        key = Key()
        self.assertEqual(key.machine(positions="XYZ").positions, "XYZ")

    def test_to_dict_round_trip(self):
        key = Key(rotors=("V", "II", "I"), reflector="C", rings="XYZ",
                  positions="ABC", plugboard="AV BS")
        again = Key.from_dict(key.to_dict())
        self.assertEqual(key, again)

    def test_random_key_is_valid(self):
        for _ in range(20):
            key = Key.random(cables=10)
            self.assertEqual(len(set(key.rotors)), 3)
            self.assertEqual(key.cable_count, 10)
            # it must be usable right away
            self.assertTrue(key.machine().encrypt("AAAA"))

    def test_offsets(self):
        key = Key(rings="BAA", positions="CAA")
        self.assertEqual(key.offsets[0], 1)

    def test_describe_uses_the_german_notation(self):
        text = Key(plugboard="AV").describe()
        self.assertIn("Walzenlage I-II-III", text)
        self.assertIn("Stecker AV", text)


if __name__ == "__main__":
    unittest.main()
