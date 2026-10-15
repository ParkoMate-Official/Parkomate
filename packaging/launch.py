"""Entry point of the packaged app (both ``ParkomateStation.exe`` and ``parkomate.exe``).

Without a command it starts the station UI; with one (``admin create``, ``doctor``,
``measuring-device`` ...) it runs that command - exactly like ``python -m parkomate``.
"""

import multiprocessing
import sys

from parkomate.cli import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
