"""Launch the local CannonChess GUI from the project root."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from cannonchess.gui import main


if __name__ == "__main__":
    main()
