"""Plugin entry point: python3 "${CLAUDE_PLUGIN_ROOT}/lib/run.py" <command> ...
Kept free of 3.11-only syntax so older interpreters reach the version check."""
import os
import sys

if sys.version_info < (3, 11):
    if sys.argv[1:3] == ["remind", "hook"]:
        sys.exit(0)  # never fail a session over the Python version
    sys.stderr.write("ai-grimoire needs Python 3.11 or newer; this is %s\n" % sys.version.split()[0])
    sys.exit(3)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from grimoire.cli import main  # noqa: E402

sys.exit(main())
