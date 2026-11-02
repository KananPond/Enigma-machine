"""Checks on the static hardware data."""

import unittest

from enigma.data import ALPHABET, REFLECTORS, ROTORS


class RotorDataTests(unittest.TestCase):
    def test_every_rotor_wiring_is_a_permutation(self):
        for name, spec in ROTORS.items():
            with self.subTest(rotor=name):
                self.assertEqual(len(spec.wiring), 26)
                self.assertEqual(sorted(spec.wiring), sorted(ALPHABET))

    def test_turnover_notches_are_letters(self):
        for name, spec in ROTORS.items():
            with self.subTest(rotor=name):
                self.assertTrue(spec.turnover)
                for letter in spec.turnover:
                    self.assertIn(letter, ALPHABET)

    def test_known_rotors_are_present(self):
        self.assertEqual(ROTORS["I"].wiring, "EKMFLGDQVZNTOWYHXUSPAIBRCJ")
        self.assertEqual(ROTORS["III"].wiring, "BDFHJLCPRTXVZNYEIWGAKMUSQO")
        self.assertEqual(ROTORS["VIII"].wiring, "FKQHTLXOCBJSPDZRAMEWNIUYGV")
        self.assertEqual(ROTORS["I"].turnover, ("Q",))
        self.assertEqual(ROTORS["II"].turnover, ("E",))
        self.assertEqual(ROTORS["III"].turnover, ("V",))
        self.assertEqual(ROTORS["IV"].turnover, ("J",))
        self.assertEqual(ROTORS["V"].turnover, ("Z",))
        self.assertEqual(len(ROTORS["VI"].turnover), 2)


class ReflectorDataTests(unittest.TestCase):
    def test_reflectors_are_fixed_point_free_involutions(self):
        for name, wiring in REFLECTORS.items():
            with self.subTest(reflector=name):
                self.assertEqual(len(wiring), 26)
                self.assertEqual(sorted(wiring), sorted(ALPHABET))
                for index, letter in enumerate(wiring):
                    # f(f(x)) == x
                    self.assertEqual(wiring[ord(letter) - 65], ALPHABET[index])
                    # no letter is connected to itself
                    self.assertNotEqual(letter, ALPHABET[index])

    def test_reflector_b_wiring(self):
        self.assertEqual(REFLECTORS["B"], "YRUHQSLDPXNGOKMIEBFZCWVJAT")


if __name__ == "__main__":
    unittest.main()
