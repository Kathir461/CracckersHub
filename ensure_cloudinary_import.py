import importlib
import sys

try:
    m = importlib.import_module("cloudinary")
    print("OK: cloudinary imported")
    print("version:", getattr(m, "__version__", "unknown"))
except Exception as e:
    print("FAIL: cannot import cloudinary")
    print(e)
    sys.exit(1)

