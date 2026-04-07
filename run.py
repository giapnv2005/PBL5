from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
WEB_DIR = PROJECT_ROOT / "Web"
if str(WEB_DIR) not in sys.path:
	sys.path.insert(0, str(WEB_DIR))

from app import app


def main() -> None:
	host = os.getenv("HOST", "0.0.0.0")
	port = int(os.getenv("PORT", "5000"))
	app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
	main()
