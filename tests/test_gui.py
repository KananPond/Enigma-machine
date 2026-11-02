"""Tests for the desktop application.

They drive the real widgets, so they need a display; when one is not
available the tests are skipped instead of failing.
"""

import unittest

try:
    import tkinter as tk

    tk.Tk()
    TK_AVAILABLE = True
except Exception:  # pragma: no cover - depends on the environment
    TK_AVAILABLE = False


class _KeyEvent:
    """Stand-in for the Tk key event."""

    def __init__(self, char: str, widget) -> None:
        self.char = char
        self.widget = widget


@unittest.skipUnless(TK_AVAILABLE, "no display available")
class EnigmaAppTests(unittest.TestCase):
    def setUp(self):
        from enigma_gui.app import EnigmaApp

        self.app = EnigmaApp()
        self.app.update()

    def tearDown(self):
        self.app.destroy()

    # ---------------------------------------------------------- keyboard
    def test_the_keyboard_binding_is_installed(self):
        self.assertTrue(self.app.bind("<KeyPress>"))

    def test_physical_keyboard_presses_the_machine(self):
        self.app.focus_force()
        self.app.update()
        self.app.event_generate("<KeyPress>", keysym="a")
        self.app.update()
        self.assertEqual(self.app._keyed_output, ["B"])
        self.assertEqual(self.app.machine.positions, "AAB")

    def test_physical_keyboard_is_case_insensitive(self):
        self.app.focus_force()
        self.app.update()
        self.app.event_generate("<KeyPress>", keysym="A")
        self.app.update()
        self.assertEqual(len(self.app._keyed_output), 1)

    def test_several_keys_advance_the_machine(self):
        self.app.focus_force()
        self.app.update()
        for keysym in ("a", "b", "c"):
            self.app.event_generate("<KeyPress>", keysym=keysym)
            self.app.update()
        self.assertEqual(self.app._keyed_output, ["B", "J", "E"])

    def test_non_letters_do_not_press_the_keys(self):
        self.app._on_physical_key(_KeyEvent("1", self.app))
        self.app._on_physical_key(_KeyEvent("", self.app))
        self.assertEqual(self.app._keyed_output, [])

    def test_typing_in_the_message_field_does_not_press_the_keys(self):
        self.app.plain_text.focus_set()
        self.app._on_physical_key(_KeyEvent("H", self.app.plain_text))
        self.assertEqual(self.app._keyed_output, [])

    def test_clicking_a_key_presses_it(self):
        self.app.keyboard._keys["Q"].invoke()
        self.app.update()
        self.assertEqual(len(self.app._keyed_output), 1)

    # --------------------------------------------------------- messaging
    def _run_job(self):
        """Let the chunked job finish."""
        for _ in range(2000):
            self.app.update()
            if self.app._job is None:
                break

    def test_message_is_prepared_and_enciphered(self):
        self.app.plain_text.insert("1.0", "ATTACK AT DAWN")
        self.app._encrypt_message()
        self._run_job()

        prepared = self.app.prepared_text.get("1.0", "end").strip()
        self.assertEqual(prepared, "ATTACKXATXDAWN")
        cipher = self.app.cipher_text.get("1.0", "end").strip()
        # 12 letters plus the two spaces that became the substitute letter
        self.assertEqual(len(cipher), 14)
        self.assertTrue(cipher.isalpha())

    def test_numbers_are_written_out(self):
        self.app.plain_text.insert("1.0", "1932")
        self.app._encrypt_message()
        self._run_job()
        self.assertEqual(
            self.app.prepared_text.get("1.0", "end").strip(), "NINETEENXTHIRTYXTWO"
        )

    def test_long_numbers_are_kept_exact(self):
        self.app.plain_text.insert("1.0", "48152")
        self.app._encrypt_message()
        self._run_job()
        self.assertEqual(
            self.app.prepared_text.get("1.0", "end").strip(), "FOUREIGHTONEFIVETWO"
        )

    def test_batch_splits_on_blank_lines(self):
        self.app.split_messages.set(True)
        self.app.plain_text.insert("1.0", "AAAA\n\nBBBB")
        self.app._encrypt_message()
        self._run_job()
        cipher = self.app.cipher_text.get("1.0", "end").strip()
        self.assertEqual(len(cipher.split("\n\n")), 2)

    def test_batch_can_restart_the_rotors(self):
        self.app.split_messages.set(True)
        self.app.restart_rotors.set(True)
        self.app.plain_text.insert("1.0", "AAAA\n\nAAAA")
        self.app._encrypt_message()
        self._run_job()
        cipher = self.app.cipher_text.get("1.0", "end").strip()
        first, second = cipher.split("\n\n")
        # with the rotors restarted both blocks are enciphered identically
        self.assertEqual(first, second)

    def test_long_text_is_processed_in_chunks(self):
        self.app.plain_text.insert("1.0", "ATTACK " * 2000)
        self.app._encrypt_message()
        self._run_job()
        cipher = self.app.cipher_text.get("1.0", "end").strip()
        # 2000 times "ATTACK" plus the space that stands in for each blank
        self.assertEqual(len(cipher), 14000)
        self.assertIn("letters", self.app.stats_label.cget("text"))

    def test_group_in_fives(self):
        self.app.plain_text.insert("1.0", "ATTACKATDAWN")
        self.app._encrypt_message()
        self._run_job()
        self.app._group_message()
        grouped = self.app.cipher_text.get("1.0", "end").strip()
        self.assertEqual(len(grouped.split()), 3)

    def test_plugboard_round_trip_through_the_gui(self):
        self.app._plug_changed("A", "V")
        self.app.update()
        self.assertEqual(self.app.machine.plugboard.paired_with("A"), "V")
        self.assertIn("AV", self.app.plug_summary.cget("text"))

    def test_duplicate_rotor_swaps(self):
        # "IV" is not in the machine yet, so it is simply fitted
        self.app._rotor_changed(1, "IV")
        self.app.update()
        self.assertEqual(self.app.machine.rotor_names, ("I", "IV", "III"))
        # now "IV" is already installed: choosing it again swaps the wheels
        self.app._rotor_changed(0, "IV")
        self.app.update()
        self.assertEqual(self.app.machine.rotor_names, ("IV", "I", "III"))


if __name__ == "__main__":
    unittest.main()
