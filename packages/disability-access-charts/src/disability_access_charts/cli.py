"""``disability-access-charts check FILE...``: audit chart documents or Plotly figure JSON.

Exit status: 0 if every chart passes, 1 if any chart fails (with ``--strict``, warnings
count as failures), 2 if a file cannot be read.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from disability_access_charts._version import __version__
from disability_access_charts.audit import audit


def _check(paths: Sequence[Path], strict: bool) -> int:
    status = 0
    for path in paths:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            result = audit(doc)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            print(f"{path}: cannot read: {exc}", file=sys.stderr)
            status = 2
            continue
        failed = [c for c in result["checks"] if not c["passed"]]
        bad = not result["passed"] or (strict and failed)
        print(f"{path}: {'FAILED' if bad else 'passed'}")
        for c in failed:
            where = f" [{c['theme']}]" if "theme" in c else ""
            wcag = f" (WCAG {c['wcag']})" if c.get("wcag") not in (None, "n/a") else ""
            print(f"  {c['severity']}: {c['id']}{wcag}{where}: {c['description']}")
            for p in c.get("problems", []):
                if isinstance(p, dict):
                    number = f" {p['number']}:" if p.get("number") else ""
                    print(f'    -{number} {p["reason"]} -- "{p["clause"]}"')
                    if p.get("suggestion"):
                        print(f"      suggestion: {p['suggestion']}")
                else:
                    print(f"    - {p}")
        if bad and status == 0:
            status = 1
    return status


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="disability-access-charts",
        description="Accessible charts whose alt-text is checked against their data.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="audit chart documents or Plotly figure JSON")
    check.add_argument("files", nargs="+", type=Path, metavar="FILE")
    check.add_argument("--strict", action="store_true", help="fail on warnings too")
    args = parser.parse_args(argv)
    return _check(args.files, args.strict)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
