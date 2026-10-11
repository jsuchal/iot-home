"""Local preview imports the exact renderer used by the add-on."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addon"))
from weatherman import Weatherman as WeathermanPreview, MDI, rounded_temperature, temperature_color, prepare_data, main

if __name__ == "__main__":
    main()
