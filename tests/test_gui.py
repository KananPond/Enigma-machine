"""Tests for the desktop window: the machine, the panels and the jobs.

The window is a real Tk window, so these tests need a display; on a headless
machine they are skipped instead of failing.
"""

import time
import unittest

try:
    import tkinter as tk

    from enigma_gui.app import EnigmaApp
    from enigma_gui.theme import Fonts  # noqa: F401  (import check only)

    HAS_TK = True
except Exception:  # pragma: no cover - depends on the environment
    HAS_TK = False


def pump(app, seconds: float = 0.05) -> None:
    end = time.time() + seconds
    while time.time() < end:
        app.update()
        time.sleep(0.01)


def wait_for_job(app, timeout: float = 120.0) -> None:
    end = time.time() + timeout
    while app.job is not None and time.time() < end:
        app.update()
        time.sleep(0.02)
    pump(app, 0.3)


@unittest.skipUnless(HAS_TK, "Tk is not available")
class GuiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = EnigmaApp()
        cls.app.geometry("1460x920+0+0")
        cls.app.update()

    @classmethod
    def tearDownClass(cls):
        cls.app.destroy()

    def setUp(self):
        self.app.apply_key(__import__("enigma").Key())
        pump(self.app)

    # ------------------------------------------------------------- machine
    def test_pressing_a_key_steps_the_rotors(self):
        self.app.press("A")
        self.assertEqual(self.app.state()["positions"], "AAB")
        self.assertIsNotNone(self.app.lampboard.lit)

    def test_a_letter_is_never_enciphered_to_itself(self):
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            self.app.apply_key(self.app.key)
            self.app.press(letter)
            self.assertNotEqual(self.app.lampboard.lit, letter)

    def test_reference_vector(self):
        self.app.set_direction("encrypt")
        self.app.msg_input.delete("1.0", "end")
        self.app.msg_input.insert("1.0", "AAAAA")
        self.app.run_message()
        self.assertEqual(self.app.last_output, "BDZGO")

    def test_encrypting_then_decrypting_returns_the_message(self):
        self.app.set_direction("encrypt")
        self.app.msg_input.delete("1.0", "end")
        self.app.msg_input.insert("1.0", "ATTACK AT DAWN")
        self.app.run_message()
        cipher = self.app.last_output

        self.app.set_direction("decrypt")
        self.app.msg_input.delete("1.0", "end")
        self.app.msg_input.insert("1.0", cipher)
        self.app.run_message()
        self.assertIn("ATTACKXATXDAWN", self.app.last_output)

    def test_rotor_change_swaps_a_duplicate(self):
        self.app.on_rotor(0, "II")  # II is already in the middle
        self.assertEqual(sorted(self.app.state()["rotors"]), ["I", "II", "III"])
        self.assertEqual(len(set(self.app.state()["rotors"])), 3)

    def test_window_and_ring_steppers(self):
        self.app.on_window(0, 1)
        self.assertEqual(self.app.state()["positions"][0], "B")
        self.app.on_ring(2, 1)
        self.assertEqual(self.app.state()["rings"][2], "B")

    # ----------------------------------------------------------- plugboard
    def test_sockets_connect_and_disconnect(self):
        self.app.on_socket("A")
        self.app.on_socket("V")
        self.assertEqual(self.app.state()["plugboard"], "AV")

        self.app.on_socket("A")  # clicking a plugged letter pulls the cable
        self.assertEqual(self.app.state()["plugboard"], "")

    def test_a_letter_cannot_take_two_cables(self):
        # clicking a plugged letter always pulls its cable first, so the
        # conflict has to come in through the text field
        self.app.on_socket("A")
        self.app.on_socket("V")
        self.app.plug_entry.delete(0, "end")
        self.app.plug_entry.insert(0, "AB AC")
        self.app.apply_plugboard_text()
        self.assertEqual(self.app.state()["plugboard"], "AV")

    def test_plugboard_text_is_applied(self):
        self.app.plug_entry.delete(0, "end")
        self.app.plug_entry.insert(0, "AV BS CG")
        self.app.apply_plugboard_text()
        self.assertEqual(self.app.state()["cables"], 3)

    def test_a_bad_plugboard_says_so(self):
        self.app.plug_entry.delete(0, "end")
        self.app.plug_entry.insert(0, "AV A")
        self.app.apply_plugboard_text()
        self.assertEqual(self.app.state()["cables"], 0)

    def test_clear_plugboard(self):
        self.app.rebuild(plugboard="AV BS")
        self.app.clear_plugboard()
        self.assertEqual(self.app.state()["plugboard"], "")

    # --------------------------------------------------------------- tabs
    def test_tabs_switch(self):
        self.app.switch_tab("break")
        self.assertTrue(self.app.panels["break"].winfo_ismapped())
        self.app.switch_tab("message")
        self.assertFalse(self.app.panels["break"].winfo_ismapped())

    # ------------------------------------------------------------- decode
    def test_decode_panel_restores_words(self):
        self.app.apply_key(self.app.key.with_(positions="AAA", plugboard="AV BS CG"))
        self.app.set_direction("encrypt")
        self.app.msg_input.delete("1.0", "end")
        self.app.msg_input.insert("1.0", "ATTACK AT DAWN")
        self.app.run_message()
        cipher = self.app.last_output

        self.app.dec_input.delete("1.0", "end")
        self.app.dec_input.insert("1.0", cipher)
        self.app.run_decode()
        pump(self.app, 0.2)
        self.assertIn("ATTACK", self.app.dec_output.get("1.0", "end"))

    # -------------------------------------------------------------- break
    def test_breaking_the_training_message(self):
        from enigma.samples import get

        sample = get("training")
        self.app.switch_tab("break")
        self.app.brk_input.delete("1.0", "end")
        self.app.brk_input.insert("1.0", sample.ciphertext)
        self.app.brk_crib.delete(0, "end")
        self.app.brk_crib.insert(0, "ATTACK AT DAWN")
        self.app.brk_offset.delete(0, "end")
        self.app.brk_offset.insert(0, "0")
        self.app.brk_rings.delete(0, "end")
        self.app.brk_rings.insert(0, "AAA")
        self.app.choice_scope.value = "quick"

        self.app.run_break()
        wait_for_job(self.app, timeout=90)
        self.assertIsNotNone(self.app.break_result)
        self.assertIn("I-II-III", self.app.brk_key.cget("text"))
        self.assertIn("ATTACK", self.app.brk_text.get("1.0", "end"))

    def test_a_short_ciphertext_is_refused(self):
        self.app.brk_input.delete("1.0", "end")
        self.app.brk_input.insert("1.0", "ABC")
        self.app.run_break()
        self.assertIsNone(self.app.job)

    # ------------------------------------------------------------ keycard
    def test_sample_loads_into_the_break_panel(self):
        from enigma.samples import get
        from enigma_gui import app as app_module

        sample = get("africa")
        window = tk.Toplevel(self.app)
        asked = {}

        def fake_ask(title, message):
            asked["title"] = title
            return False

        original = app_module.messagebox.askyesno
        app_module.messagebox.askyesno = fake_ask
        try:
            self.app._load_sample(sample, window)
        finally:
            app_module.messagebox.askyesno = original

        self.assertIn("载入示例", asked.get("title", ""))
        self.assertIn(sample.ciphertext[:10], self.app.brk_input.get("1.0", "end"))
        self.assertIn(sample.key.rings, self.app.brk_rings.get())

    def test_random_key_is_applied(self):
        from enigma.keys import Key
        from enigma.plugboard import Plugboard

        key = Key.random(cables=Plugboard.MAX_PAIRS)
        self.app.apply_key(key)
        self.assertEqual(self.app.state()["cables"], 10)
        self.assertEqual(self.app.state()["positions"], key.positions)


if __name__ == "__main__":
    unittest.main()
