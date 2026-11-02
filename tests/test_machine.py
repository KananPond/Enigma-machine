"""Reference vector tests for the Enigma simulation.

The vectors are the ones published with the Enigma literature (Wikipedia's
"normalized Enigma sequences" and the worked examples that accompany them).
"""

import unittest

from enigma import EnigmaMachine, Plugboard, PlugboardError
from enigma.machine import Rotor
from enigma.data import ROTORS


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


class ReferenceVectorTests(unittest.TestCase):
    def test_five_peated_letters(self):
        """Rotors I-II-III, reflector B, rings AAA, start AAA: AAAAA -> BDZGO."""
        self.assertEqual(machine().encrypt("AAAAA"), "BDZGO")

    def test_full_alphabet(self):
        """The same machine over a whole alphabet, which exercises a turnover."""
        expected = "BDZGOWCXLTKSBTMCDLPBMUQOFX"
        self.assertEqual(machine().encrypt("A" * 26), expected)

    def test_ring_settings_shift_the_cipher(self):
        """Ringstellung 02 02 02 (i.e. 'B' on every rotor) gives EWTYX."""
        eng = machine(ring_settings=("B", "B", "B"))
        self.assertEqual(eng.encrypt("AAAAA"), "EWTYX")

    def test_encryption_is_reciprocal(self):
        eng = machine()
        ciphertext = eng.encrypt("ATTACKATDAWN")
        eng.set_positions("AAA")
        self.assertEqual(eng.encrypt(ciphertext), "ATTACKATDAWN")

    def test_normalized_stepping_sequence(self):
        """Wikipedia's normalized sequence: ADU -> ADV -> AEW -> BFX -> BFY."""
        eng = machine(positions=("A", "D", "U"))
        seen = []
        for _ in range(4):
            eng.press("A")
            seen.append(eng.positions)
        self.assertEqual(seen, ["ADV", "AEW", "BFX", "BFY"])

    def test_letter_never_encrypts_to_itself(self):
        """Without a plugboard no letter can be enciphered as itself."""
        eng = machine(positions=("A", "A", "A"))
        for _ in range(6):
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                self.assertNotEqual(eng.press(letter), letter)
            eng.set_positions("AAA")


class RotorMathTests(unittest.TestCase):
    def test_forward_and_reverse_are_inverse(self):
        for name, spec in ROTORS.items():
            rotor = Rotor(spec, position=7, ring=3)
            for letter in range(26):
                with self.subTest(rotor=name, letter=letter):
                    self.assertEqual(rotor.reverse(rotor.forward(letter)), letter)

    def test_ring_setting_shifts_the_wiring(self):
        rotor = Rotor(ROTORS["I"], position=0, ring=0)
        self.assertEqual(rotor.forward(0), ord("E") - 65)
        rotor.ring = 1
        # Wikipedia: "Where rotor I in the A-position normally encodes an A
        # into an E, with a ring setting offset B-02 it will be encoded into K."
        self.assertEqual(rotor.forward(0), ord("K") - 65)

    def test_position_changes_the_wiring(self):
        rotor = Rotor(ROTORS["I"])
        first = rotor.forward(0)
        rotor.step()
        self.assertNotEqual(first, rotor.forward(0))


class PlugboardTests(unittest.TestCase):
    def test_pairs_are_symmetric(self):
        board = Plugboard({"A": "V", "B": "S"})
        self.assertEqual(board.paired_with("A"), "V")
        self.assertEqual(board.paired_with("V"), "A")
        self.assertEqual(board.pair_count, 2)

    def test_plugging_removes_the_previous_cable(self):
        board = Plugboard({"A": "V"})
        board.set_pair("A", "B")
        self.assertEqual(board.paired_with("A"), "B")
        self.assertIsNone(board.paired_with("V"))
        self.assertEqual(board.pair_count, 1)

    def test_toggle(self):
        board = Plugboard()
        board.toggle("A", "B")
        self.assertEqual(board.paired_with("A"), "B")
        board.toggle("A", "B")
        self.assertIsNone(board.paired_with("A"))

    def test_a_letter_cannot_be_plugged_into_itself(self):
        with self.assertRaises(PlugboardError):
            Plugboard({"A": "A"})

    def test_maximum_of_ten_cables(self):
        board = Plugboard()
        pairs = "AV BS CG DL FU HZ IN KM OW RX".split()
        for first, second in pairs:
            board.set_pair(first, second)
        self.assertEqual(board.pair_count, 10)
        with self.assertRaises(PlugboardError):
            board.set_pair("E", "J")

    def test_parse(self):
        board = Plugboard.parse("av bs cg")
        self.assertEqual(board.describe(), "AV BS CG")


class MachineApiTests(unittest.TestCase):
    def test_settings_round_trip(self):
        eng = machine()
        eng.set_positions("ADU")
        eng.set_ring_settings("BLQ")
        self.assertEqual(eng.positions, "ADU")
        self.assertEqual(eng.ring_settings, "BLQ")

    def test_wrong_number_of_letters_is_rejected(self):
        eng = machine()
        with self.assertRaises(ValueError):
            eng.set_positions("AA")
        with self.assertRaises(ValueError):
            eng.set_ring_settings("AAAA")

    def test_non_letters_are_ignored(self):
        eng = machine()
        self.assertEqual(eng.encrypt("A A-A, A! A"), "BDZGO")

    def test_plugboard_changes_the_result(self):
        plain = machine()
        plugged = machine(plugboard=Plugboard({"A": "B"}))
        self.assertNotEqual(plain.encrypt("AAAAA"), plugged.encrypt("AAAAA"))

    def test_trace_records_the_signal_path(self):
        eng = machine()
        trace = []
        eng.press("A", trace=trace)
        stages = [step.stage for step in trace]
        self.assertEqual(stages[0], "key")
        self.assertEqual(stages[1], "plugboard")
        self.assertIn("reflector", stages)
        self.assertEqual(stages[-1], "plugboard")
        # the signal visits the three rotors twice: forward and back
        rotor_visits = [s for s in stages if s in {"I", "II", "III"}]
        self.assertEqual(len(rotor_visits), 6)

    def test_machine_describes_itself(self):
        eng = machine()
        eng.set_positions("ADU")
        description = eng.describe()
        self.assertIn("Reflector B", description)
        self.assertIn("ADU", description)


if __name__ == "__main__":
    unittest.main()
