# SPDX-License-Identifier: GPL-3.0-or-later
"""Entry point `python -m alba`."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
