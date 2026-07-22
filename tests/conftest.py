import sys, importlib.util
from pathlib import Path

# ha-tui.py has a hyphen so can't be imported normally
_spec = importlib.util.spec_from_file_location(
    "ha_tui", Path(__file__).parent.parent / "ha-tui.py"
)
_module = importlib.util.module_from_spec(_spec)
sys.modules["ha_tui"] = _module
_spec.loader.exec_module(_module)
