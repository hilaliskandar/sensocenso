# Test-time stub to avoid importing pyarrow on Windows CI/dev boxes
import sys

class _Stub:
    __all__ = []
    __version__ = "0.0.0"

# If pyarrow import causes fatal errors on this environment, stub it
if 'pyarrow' not in sys.modules:
    sys.modules['pyarrow'] = _Stub()
