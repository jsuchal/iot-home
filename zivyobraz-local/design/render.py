#!/usr/bin/env python3
"""Preview CLI using the same components as the add-on."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addon"))
from components import Components, main

if __name__ == "__main__":
    # Preserve the preview CLI defaults after moving shared components.
    if "--data" not in sys.argv:
        sys.argv.extend(["--data", str(Path(__file__).with_name("demo.json"))])
    if "--output" not in sys.argv:
        sys.argv.extend(["--output", str(Path(__file__).with_name("preview.png"))])
    main()
