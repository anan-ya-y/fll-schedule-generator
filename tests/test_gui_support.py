from __future__ import annotations

from pathlib import Path
import sys
from types import ModuleType
import unittest

# The Linux optimizer test environment may omit Tk. These tests only import and
# exercise the GUI's non-window file helpers.
try:
    import tkinter  # noqa: F401
except ModuleNotFoundError:
    class _Widget:
        pass

    tkinter_stub = ModuleType("tkinter")
    tkinter_stub.Tk = _Widget
    ttk_stub = ModuleType("tkinter.ttk")
    ttk_stub.Frame = _Widget
    filedialog_stub = ModuleType("tkinter.filedialog")
    messagebox_stub = ModuleType("tkinter.messagebox")
    tkinter_stub.filedialog = filedialog_stub
    tkinter_stub.messagebox = messagebox_stub
    tkinter_stub.ttk = ttk_stub
    sys.modules.update(
        {
            "tkinter": tkinter_stub,
            "tkinter.ttk": ttk_stub,
            "tkinter.filedialog": filedialog_stub,
            "tkinter.messagebox": messagebox_stub,
        }
    )

from scheduler_gui import existing_file, load_tournament_details, validate_tournament_date


class GuiSupportTests(unittest.TestCase):
    def test_date_is_normalized(self) -> None:
        self.assertEqual(validate_tournament_date("01/02/2027"), "1/2/2027")

    def test_explicit_team_list_overrides_details_value(self) -> None:
        folder = Path("examples/4-team").resolve()
        team_list = folder / "teamlist.csv"
        details = load_tournament_details(
            folder / "tournament_details.json",
            team_list,
        )
        self.assertEqual(details["teamlist"], str(team_list))

    def test_missing_file_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not exist"):
            existing_file("missing-config.json", "config.json")


if __name__ == "__main__":
    unittest.main()
