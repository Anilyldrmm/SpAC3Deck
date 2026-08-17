import sys
from pathlib import Path

# Add project root to sys.path so that macrodeck module can be imported
sys.path.insert(0, str(Path(__file__).parent.parent))
