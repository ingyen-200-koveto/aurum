from __future__ import annotations

import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

try:
    from dashboard.app import app
except ImportError as error:
    print("=" * 60)
    print("AURUM DASHBOARD IMPORT HIBA")
    print("=" * 60)
    print(f"Hiba: {error}")
    print()
    print("Ellenőrizd, hogy létezik:")
    print(PROJECT_DIR / "dashboard" / "__init__.py")
    print(PROJECT_DIR / "dashboard" / "app.py")
    print("=" * 60)
    raise SystemExit(1) from error


HOST = "127.0.0.1"
PORT = 5055


if __name__ == "__main__":
    print("=" * 60)
    print("AURUM WEB DASHBOARD")
    print(f"Cím: http://{HOST}:{PORT}")
    print("Leállítás: CTRL + C")
    print("=" * 60)

    try:
        app.run(
            host=HOST,
            port=PORT,
            debug=False,
            threaded=True,
            use_reloader=False,
        )
    except PermissionError as error:
        print()
        print("=" * 60)
        print("PORT HOZZÁFÉRÉSI HIBA")
        print("=" * 60)
        print(f"Hiba: {error}")
        print()
        print(f"A Windows nem engedi a {PORT}-es port használatát.")
        print("Próbáld meg rendszergazdai PowerShellből indítani,")
        print("vagy állíts be egy másik portot a fájlban.")
        print("=" * 60)
        raise SystemExit(1) from error
    except OSError as error:
        print()
        print("=" * 60)
        print("DASHBOARD HÁLÓZATI HIBA")
        print("=" * 60)
        print(f"Hiba: {error}")
        print()
        print(f"Ellenőrizd, hogy a {PORT}-es port nincs-e használatban.")
        print("=" * 60)
        raise SystemExit(1) from error