import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.database import ensure_tables_exist


def main():
    ensure_tables_exist()
    print("DB table check complete: created only missing tables.")


if __name__ == "__main__":
    main()
