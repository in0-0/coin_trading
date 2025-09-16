import json
import os
import tempfile
import unittest

from models import Position
from state_manager import StateManager


class TestStateManager(unittest.TestCase):
    def setUp(self):
        fd, self.test_file = tempfile.mkstemp(prefix="positions_", suffix=".json")
        os.close(fd)
        # Ensure empty file is removed so load_positions treats as no file
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
        self.state_manager = StateManager(state_file=self.test_file)

    def tearDown(self):
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def test_load_positions_no_file(self):
        positions = self.state_manager.load_positions()
        self.assertEqual(positions, {})

    def test_save_and_load_positions_roundtrip(self):
        pos = Position(symbol="BTCUSDT", qty=0.1, entry_price=50000.0, stop_price=49000.0)
        self.state_manager.save_positions({"BTCUSDT": pos})

        self.assertTrue(os.path.exists(self.test_file))
        with open(self.test_file, "r") as f:
            raw = json.load(f)
        self.assertIn("BTCUSDT", raw)
        self.assertEqual(raw["BTCUSDT"]["symbol"], "BTCUSDT")

        loaded = self.state_manager.load_positions()
        self.assertIn("BTCUSDT", loaded)
        self.assertIsInstance(loaded["BTCUSDT"], Position)
        self.assertAlmostEqual(loaded["BTCUSDT"].stop_price, 49000.0)

    def test_get_and_upsert_position_crud(self):
        # Initially none
        self.assertIsNone(self.state_manager.get_position("ETHUSDT"))

        # Upsert create
        pos = Position(symbol="ETHUSDT", qty=1.5, entry_price=3000.0, stop_price=2850.0)
        updated = self.state_manager.upsert_position("ETHUSDT", pos)
        self.assertIn("ETHUSDT", updated)
        self.assertIsInstance(updated["ETHUSDT"], Position)

        loaded_after = self.state_manager.load_positions()
        self.assertIn("ETHUSDT", loaded_after)

        # Upsert update
        pos2 = Position(symbol="ETHUSDT", qty=2.0, entry_price=3100.0, stop_price=2900.0)
        updated2 = self.state_manager.upsert_position("ETHUSDT", pos2)
        self.assertAlmostEqual(updated2["ETHUSDT"].qty, 2.0)

        # Upsert delete
        updated3 = self.state_manager.upsert_position("ETHUSDT", None)
        self.assertNotIn("ETHUSDT", updated3)
        self.assertIsNone(self.state_manager.get_position("ETHUSDT"))

    def test_load_positions_corrupted_file(self):
        with open(self.test_file, "w") as f:
            f.write("{not: valid json}")
        positions = self.state_manager.load_positions()
        self.assertEqual(positions, {})


if __name__ == "__main__":
    unittest.main()
