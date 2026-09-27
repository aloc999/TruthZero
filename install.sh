#!/bin/sh
# TruthZero one-line installer.
#   curl -fsSL https://raw.githubusercontent.com/aloc999/TruthZero/main/install.sh | sh
# Env: VERSION=v0.15.0 (default: latest GitHub release, fallback: main)
set -eu

REPO="aloc999/TruthZero"
VERSION="${VERSION:-}"

say() { printf '  [truthzero] %s\n' "$*"; }
die() { printf '  [truthzero] ERROR: %s\n' "$*" >&2; exit 1; }

if [ -z "$VERSION" ]; then
    if command -v curl >/dev/null 2>&1; then
        VERSION="$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" 2>/dev/null | grep '"tag_name"' | cut -d'"' -f4 || true)"
    fi
    if [ -z "$VERSION" ]; then
        VERSION="main"
        say "no release found, installing from main"
    fi
fi
say "installing $REPO@$VERSION"

SRC="git+https://github.com/$REPO.git@$VERSION"

if command -v uv >/dev/null 2>&1; then
    say "backend: uv"
    uv tool install --force "$SRC" || die "uv install failed"
elif command -v pipx >/dev/null 2>&1; then
    say "backend: pipx"
    pipx install --force "$SRC" || die "pipx install failed (try: sudo apt install pipx)"
else
    die "need uv or pipx: curl -LsSf astral.sh/uv/install.sh | sh"
fi

case ":$PATH:" in
    *":$HOME/.local/bin:"*) ;;
    *) say "NOTE: add \$HOME/.local/bin to PATH:"; say '  export PATH="$HOME/.local/bin:$PATH"' ;;
esac

if command -v truthzero >/dev/null 2>&1; then
    truthzero version 2>/dev/null | head -2 || true
    say "done. run: truthzero tui"
else
    die "installed but 'truthzero' not on PATH — add \$HOME/.local/bin to PATH, then re-login"
fi
