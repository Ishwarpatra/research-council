import sys
from pathlib import Path

# Add root directory to python path for imports (council, db, config, etc.)
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from api import app

# Vercel WSGI/ASGI entry point
__all__ = ["app"]
