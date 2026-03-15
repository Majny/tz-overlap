#!/usr/bin/env bash
# ============================================================
# Publish tz-overlap to PyPI
#
# Usage:
#   ./publish.sh <PYPI_API_TOKEN>     # pass token as argument
#   PYPI_TOKEN=pypi-... ./publish.sh  # or via env var
#
# Get a token from: https://pypi.org/manage/account/token/
# ============================================================
set -euo pipefail

cd "$(dirname "$0")"

# ---------- resolve token ----------
TOKEN="${1:-${PYPI_TOKEN:-}}"
if [ -z "$TOKEN" ]; then
    echo "ERROR: No PyPI token provided."
    echo ""
    echo "Usage:"
    echo "  $0 <PYPI_API_TOKEN>"
    echo "  PYPI_TOKEN=pypi-... $0"
    echo ""
    echo "Get a token at https://pypi.org/manage/account/token/"
    exit 1
fi

if [[ ! "$TOKEN" =~ ^pypi- ]]; then
    echo "WARNING: Token does not start with 'pypi-'. Are you sure this is correct?"
    read -p "Continue? [y/N] " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]] || exit 1
fi

# ---------- rebuild ----------
echo "==> Cleaning old dist/"
rm -rf dist/

echo "==> Building package..."
python3 -m build

echo ""
echo "==> Running twine check..."
python3 -m twine check dist/*

# ---------- upload ----------
echo ""
echo "==> Uploading to PyPI..."
TWINE_USERNAME=__token__ TWINE_PASSWORD="$TOKEN" \
    python3 -m twine upload dist/* --non-interactive

# ---------- verify ----------
echo ""
echo "==> Verifying upload..."
sleep 5
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://pypi.org/project/tz-overlap/)
if [ "$HTTP_CODE" = "200" ]; then
    echo "    SUCCESS! Package is live at https://pypi.org/project/tz-overlap/"
else
    echo "    PyPI returned HTTP $HTTP_CODE — the package may take a minute to appear."
    echo "    Check manually: https://pypi.org/project/tz-overlap/"
fi

echo ""
echo "Done. Install with:  pip install tz-overlap"
