import json
import tempfile
import unittest
from pathlib import Path

from scripts import leaderboard_watch


class LeaderboardWatchTests(unittest.TestCase):
    def test_has_leader_changed_tracks_login_only(self):
        previous = [{"login": "alice", "score": 10.0}]

        self.assertTrue(leaderboard_watch.has_leader_changed(None, previous))
        self.assertFalse(
            leaderboard_watch.has_leader_changed(previous, [{"login": "alice", "score": 4.0}])
        )
        self.assertTrue(
            leaderboard_watch.has_leader_changed(previous, [{"login": "bob", "score": 10.1}])
        )

    def test_save_leaderboard_writes_snapshot_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "leaderboard.json"
            leaderboard_watch.atomic_write_json(target, [{"login": "alice", "score": 1.5}])

            self.assertEqual(json.loads(target.read_text(encoding="utf-8"))[0]["login"], "alice")
            self.assertFalse(target.with_suffix(".json.tmp").exists())

    def test_save_leaderboard_meta_records_previous_and_current_top(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_meta_file = leaderboard_watch.LEADERBOARD_META_FILE
            leaderboard_watch.LEADERBOARD_META_FILE = Path(tmp) / "leaderboard_meta.json"
            try:
                leaderboard_watch.save_leaderboard_meta(
                    [{"login": "bob", "score": 2.0}],
                    [{"login": "alice", "score": 1.0}],
                    True,
                )

                meta = json.loads(
                    leaderboard_watch.LEADERBOARD_META_FILE.read_text(encoding="utf-8")
                )
            finally:
                leaderboard_watch.LEADERBOARD_META_FILE = old_meta_file

        self.assertEqual(meta["current_top"], {"login": "bob", "score": 2.0})
        self.assertEqual(meta["previous_top"], {"login": "alice", "score": 1.0})
        self.assertTrue(meta["issue_created"])
        self.assertIn("updated_at", meta)


if __name__ == "__main__":
    unittest.main()
