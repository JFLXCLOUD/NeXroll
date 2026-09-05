"""Version shim for the backend package.

NeXroll/version.py is the single source of truth. This file exists because
`main.py` runs with the backend directory first on sys.path, so a bare
`import version` resolves here and shadows the root module -- which is how
2.1.0-beta.3 shipped reporting itself as 2.1.0-beta.2. Reading the root file
keeps both answers identical no matter which one wins the import.

The literal below is only a fallback for frozen builds that bundle this module
without the root file beside it.
"""

import os
import re

__version__ = '2.2.0-beta.6'

_ROOT_VERSION_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'version.py'
)

try:
    if os.path.isfile(_ROOT_VERSION_FILE):
        with open(_ROOT_VERSION_FILE, 'r', encoding='utf-8-sig') as _handle:
            _match = re.search(r"""__version__\s*=\s*['"]([^'"]+)['"]""", _handle.read())
        if _match:
            __version__ = _match.group(1)
except Exception:
    pass  # Keep the bundled fallback rather than failing to start.


def get_version():
    return __version__
