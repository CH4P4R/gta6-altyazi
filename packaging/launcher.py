"""Kurulu uygulamanın (GTA6Altyazi.exe) giriş noktası."""

import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()
    if sys.argv[1:] == ["--arka-plan"]:
        from altyazi.ui.run import run_gui
        sys.exit(run_gui([sys.argv[0]], background=True))
    if len(sys.argv) > 1:
        from altyazi.__main__ import main
        sys.exit(main())
    from altyazi.ui.run import run_gui
    sys.exit(run_gui())
