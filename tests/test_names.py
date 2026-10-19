import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from app.names import load_names
from app.simulation import _roster_players, roster_for


class NameFileTests(unittest.TestCase):
    def test_text_files_preserve_spelling_and_ignore_blank_comment_duplicate_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "names.txt"
            path.write_text("# Custom names\n\n McDonald \nmcdonald\nO'Neal\nJean-Luc\nJosé\n", encoding="utf-8")
            self.assertEqual(load_names(path), ("McDonald", "O'Neal", "Jean-Luc", "José"))

    def test_empty_pool_fails_with_a_clear_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.txt"
            path.write_text("\n# No names\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Name pool is empty: empty.txt"):
                load_names(path)

    def test_bundled_names_load_when_started_outside_the_repository(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([
                sys.executable, "-c",
                "from app.names import FIRST_NAMES, LAST_NAMES; "
                "assert len(FIRST_NAMES) > 1000 and len(LAST_NAMES) >= 5000",
            ], cwd=directory, env={**os.environ, "PYTHONPATH": str(root)},
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_insufficient_combinations_fail_instead_of_retrying_forever(self):
        _roster_players.cache_clear()
        try:
            with patch("app.simulation.FIRST_NAMES", ("Only",)), patch("app.simulation.LAST_NAMES", ("Name",)):
                with self.assertRaisesRegex(ValueError, "enough combinations"):
                    roster_for("seattle")
        finally:
            _roster_players.cache_clear()
