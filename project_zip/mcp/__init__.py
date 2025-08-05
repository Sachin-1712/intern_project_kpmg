# mcp/__init__.py
import importlib
import pkgutil
from pathlib import Path


# Dynamically import every .py file inside mcp package (except base)
_pkg_path = Path(__file__).parent
for mod in pkgutil.iter_modules([str(_pkg_path)]):
    if mod.name != "base":  # skip base.py
        importlib.import_module(f"{__name__}.{mod.name}")
