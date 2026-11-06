"""Tests for the menu attack - the Enigma breaking module.

The attack is checked against machines that were really used: a message is
enciphered with a known setting and the attack has to find that setting
again, down to the plugboard.
"""

import unittest

try:
    import numpy  # noqa: F401

    NUMPY_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on the environment
    NUMPY_AVAILABLE = False

from enigma.machine import EnigmaMachine
from enigma.plugboard import Plugboard

TEXT = (
    "ATTACK AT DAWN AND DESTROY THE SUPPLY LINES BEHIND THE ENEMY "
    "POSITION THE TROOPS MUST CROSS THE RIVER BEFORE DAWN TOMORROW AND "
    "HOLD THE BRIDGE UNTIL THE REINFORCEMENTS ARRIVE FROM THE NORTH "
)

#: The crib, in the shape the machine sees it: the space became an X.
CRIB = "ATTACKXATXDAWN"

#: The wiring the test machine uses.
WIRING = "AV BS CG DL FU HZ IN KM"


def _message() -> str:
    """The test message, prepared the way the machine wants it."""
    return (TEXT * 2).replace(" ", "X")


def _cipher(
    order: tuple[str, str, str] = ("III", "II", "I"),
    reflector: str = "B",
    rings: tuple[str, str, str] = ("A", "A", "A"),
    positions: tuple[str, str, str] = ("B", "M", "U"),
    plugboard: str = WIRING,
    plain: str | None = None,
) -> str:
    """Encipher the test message with the given settings."""
    machine = EnigmaMachine.create(
        rotor_order=order,
        reflector=reflector,
        plugboard=Plugboard.parse(plugboard),
        ring_settings=rings,
        positions=positions,
    )
    return machine.encrypt(_message() if plain is None else plain)


@unittest.skipUnless(NUMPY_AVAILABLE, "numpy is not installed")
class CoreTableTests(unittest.TestCase):
    """The tables the attack is built on have to match the machine."""

    def test_the_core_table_matches_the_machine(self):
        from enigma.crack import core_table

        for order in (("III", "II", "I"), ("I", "II", "III"), ("V", "IV", "II")):
            for reflector in ("B", "C"):
                table = core_table(order, reflector)
                machine = EnigmaMachine.create(
                    rotor_order=order, reflector=reflector
                )
                for positions in ("AAA", "BMU", "QHZ", "ZZZ"):
                    machine.set_positions(positions)
                    machine.step_rotors()
                    expected = machine.core_permutation()
                    offset_left = machine.rotors[0].offset
                    offset_middle = machine.rotors[1].offset
                    offset_right = machine.rotors[2].offset
                    self.assertEqual(
                        list(table[offset_left, offset_middle, offset_right]),
                        expected,
                        msg=f"{order} {reflector} {positions}",
                    )

    def test_the_stepping_matches_the_machine(self):
        from enigma.crack import _Stepping

        order = ("III", "II", "I")
        machine = EnigmaMachine.create(rotor_order=order)
        machine.set_positions("BMU")
        stepping = _Stepping(order, (0, 0, 0))
        state = 1 * 676 + 12 * 26 + 20

        for index, offsets in enumerate(stepping):
            machine.step_rotors()
            self.assertEqual(
                tuple(int(value[state]) for value in offsets),
                tuple(rotor.offset for rotor in machine.rotors),
                msg=f"character {index}",
            )
            if index > 40:
                break


@unittest.skipUnless(NUMPY_AVAILABLE, "numpy is not installed")
class MenuAttackTests(unittest.TestCase):
    """The attack has to find the settings a message was really made with."""

    def test_the_attack_finds_the_rotors_and_the_start(self):
        from enigma.crack import menu_attack

        cipher = _cipher()
        findings = menu_attack(
            cipher,
            CRIB,
            offsets=[0],
            rotor_names=("I", "II", "III"),
            reflectors=("B",),
        )

        self.assertTrue(findings)
        found = [
            item
            for item in findings
            if item.rotor_order == ("III", "II", "I") and item.positions == "BMU"
        ]
        self.assertTrue(found, msg="the real setting did not survive")
        self.assertEqual(found[0].reflector, "B")
        self.assertEqual(found[0].crib_offset, 0)

    def test_the_attack_finds_the_plugboard_cables(self):
        from enigma.crack import crib_matches, menu_attack

        cipher = _cipher()
        findings = menu_attack(
            cipher,
            CRIB,
            offsets=[0],
            rotor_names=("I", "II", "III"),
            reflectors=("B",),
        )
        found = [
            item
            for item in findings
            if item.rotor_order == ("III", "II", "I") and item.positions == "BMU"
        ]
        self.assertTrue(found)

        # several wirings survive the attack; the one that deciphers the crib
        # letter by letter is the right one
        best = max(found, key=lambda item: crib_matches(item, cipher, CRIB))
        self.assertEqual(crib_matches(best, cipher, CRIB), len(CRIB))

        real = set(Plugboard.parse(WIRING).pairs)
        derived = set(best.plugboard_pairs)
        self.assertTrue(derived)
        self.assertTrue(
            derived.issubset(real),
            msg=f"the attack invented cables: {derived - real}",
        )
        # every cable of the crib that can be seen has to be found
        self.assertGreaterEqual(len(derived), 5)

    def test_the_attack_finds_the_position_of_the_crib(self):
        """The crib sits in the middle of the message and is found there."""
        from enigma.crack import menu_attack

        filler = "XYZW" * 5
        plain = filler + CRIB + filler
        cipher = _cipher(plain=plain)
        start = len(filler)

        findings = menu_attack(
            cipher,
            CRIB,
            offsets=None,
            rotor_names=("I", "II", "III"),
            reflectors=("B",),
            orders=[("III", "II", "I")],
        )
        offsets = {item.crib_offset for item in findings}
        self.assertIn(start, offsets)

        # the setting that survives at that place is the real one
        found = [item for item in findings if item.crib_offset == start]
        self.assertTrue(
            any(item.positions == "BMU" for item in found),
            msg=f"the real setting was not found at offset {start}",
        )

    def test_a_wrong_crib_is_not_reported_as_the_truth(self):
        from enigma.crack import menu_attack

        cipher = _cipher()
        findings = menu_attack(
            cipher,
            "QWERTYUIOPAS",
            offsets=[0],
            rotor_names=("I", "II", "III"),
            reflectors=("B",),
        )
        for item in findings:
            self.assertNotEqual(
                (item.rotor_order, item.positions),
                (("III", "II", "I"), "BMU"),
                msg="a wrong crib must not point at the real setting",
            )

    def test_the_attack_works_with_other_machines(self):
        """The attack is not tuned to one particular machine."""
        from enigma.crack import menu_attack

        cases = [
            (("I", "II", "III"), "B", ("A", "A", "A"), "AAL", "AT BL CG"),
            (("II", "IV", "I"), "C", ("A", "A", "A"), "QQZ", "AQ BR CS"),
            (("V", "III", "II"), "B", ("A", "A", "A"), "BTW", "AM BN CO DP"),
        ]
        for order, reflector, rings, positions, wiring in cases:
            with self.subTest(order=order, reflector=reflector, positions=positions):
                machine = EnigmaMachine.create(
                    rotor_order=order,
                    reflector=reflector,
                    plugboard=Plugboard.parse(wiring),
                    ring_settings=rings,
                    positions=positions,
                )
                cipher = machine.encrypt(_message())
                findings = menu_attack(
                    cipher,
                    CRIB,
                    offsets=[0],
                    rotor_names=("I", "II", "III", "IV", "V"),
                    reflectors=(reflector,),
                    ring_settings=rings,
                    orders=[order],
                )
                real = set(Plugboard.parse(wiring).pairs)
                found = [
                    item
                    for item in findings
                    if item.rotor_order == order
                    and item.positions == positions
                    and item.plugboard_pairs
                    and set(item.plugboard_pairs).issubset(real)
                ]
                self.assertTrue(
                    found,
                    msg=f"the real setting of {order} {reflector} {positions} "
                    f"did not survive",
                )


@unittest.skipUnless(NUMPY_AVAILABLE, "numpy is not installed")
class BreakTests(unittest.TestCase):
    """The whole break: rotors, plugboard and readable text."""

    def test_the_key_is_found_completely(self):
        from enigma.crack import break_enigma

        result = break_enigma(
            _cipher(),
            CRIB,
            offsets=[0],
            rotor_names=("I", "II", "III"),
            reflectors=("B",),
            max_candidates=3,
        )

        self.assertIsNotNone(result.finding)
        self.assertEqual(result.finding.rotor_order, ("III", "II", "I"))
        self.assertEqual(result.finding.reflector, "B")
        self.assertEqual(result.finding.positions, "BMU")
        self.assertEqual(
            set(result.plugboard.pairs),
            set(Plugboard.parse(WIRING).pairs),
        )
        self.assertIn("ATTACK", result.text)
        self.assertTrue(result.confident)

    def test_the_text_starts_with_the_real_plaintext(self):
        from enigma.crack import break_enigma

        result = break_enigma(
            _cipher(),
            CRIB,
            offsets=[0],
            rotor_names=("I", "II", "III"),
            reflectors=("B",),
            max_candidates=3,
        )
        self.assertTrue(result.text.upper().startswith("ATTACK"))

    def test_a_short_crib_is_refused(self):
        from enigma.crack import menu_attack

        with self.assertRaises(ValueError):
            menu_attack(_cipher(), "AB", offsets=[0])

    def test_the_plugboard_map_is_closed_under_the_involution(self):
        """A cable has to be written down in both directions.

        The crib graph only knows the letters that really appear in it, so a
        map can name a partner that is not a node of the graph.  The plugboard
        is an involution, so the way back is known as well and has to be used
        - otherwise the deciphered letters come out wrong.
        """
        from enigma.crack import _closed

        # A is plugged to V, V is not part of the graph
        closed = _closed({0: 21})
        self.assertEqual(closed[0], 21)
        self.assertEqual(closed[21], 0)

        # a self connection is not a cable
        self.assertEqual(_closed({5: 5}), {})

        # a contradiction is dropped instead of being papered over
        closed = _closed({0: 21, 21: 7})
        self.assertEqual(closed[0], 21)
        self.assertEqual(closed[21], 0)
        self.assertNotIn(7, closed)

    def test_the_crib_is_deciphered_letter_by_letter(self):
        """The finding that survives really deciphers the crib."""
        from enigma.crack import crib_matches, menu_attack

        cipher = _cipher()
        findings = menu_attack(
            cipher,
            CRIB,
            offsets=[0],
            rotor_names=("I", "II", "III"),
            reflectors=("B",),
        )
        found = [
            item
            for item in findings
            if item.rotor_order == ("III", "II", "I") and item.positions == "BMU"
        ]
        self.assertTrue(found)
        best = max(found, key=lambda item: crib_matches(item, cipher, CRIB))
        self.assertEqual(crib_matches(best, cipher, CRIB), len(CRIB))

    def test_the_ring_settings_are_taken_as_given(self):
        from enigma.crack import break_enigma

        result = break_enigma(
            _cipher(rings=("B", "M", "U")),
            CRIB,
            offsets=[0],
            rotor_names=("I", "II", "III"),
            reflectors=("B",),
            ring_settings=("B", "M", "U"),
            max_candidates=3,
        )
        self.assertIsNotNone(result.finding)
        self.assertEqual(result.finding.rotor_order, ("III", "II", "I"))
        self.assertEqual(result.finding.positions, "BMU")
        self.assertIn("ATTACK", result.text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
