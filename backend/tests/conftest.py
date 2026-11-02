import sys
from pathlib import Path

# Tambahkan backend/ ke sys.path agar `import repo`, `import core...` bisa diakses dari tests/
sys.path.insert(0, str(Path(__file__).parent.parent))
