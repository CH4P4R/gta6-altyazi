import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os  # noqa: E402
import tempfile  # noqa: E402

# Testler kullanıcının gerçek ayar klasörüne yazmasın
os.environ.setdefault("ALTYAZI_DATA", tempfile.mkdtemp(prefix="altyazi-test-"))
