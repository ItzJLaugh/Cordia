#!/usr/bin/env bash
# cordia-ops installer — local operator tooling only.
#
# Installs a Rust toolchain via rustup if cargo is missing, builds the release
# binary, and (with --install) drops it at /usr/local/bin/cordia-ops.
#
# This touches nothing under /opt/cordia/web and configures no web server.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_PATH="/usr/local/bin/cordia-ops"
DO_INSTALL=0
[[ "${1:-}" == "--install" ]] && DO_INSTALL=1

say() { printf '\033[0;32m==>\033[0m %s\n' "$*"; }
die() { printf '\033[0;31mxx \033[0m %s\n' "$*" >&2; exit 1; }

# --- 1. C toolchain (rustc needs a linker) ---------------------------------
if ! command -v cc >/dev/null 2>&1; then
  say "no C linker found; installing build-essential"
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -qq && sudo apt-get install -y build-essential
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y gcc
  else
    die "install a C toolchain (gcc) manually, then re-run"
  fi
fi

# --- 2. Rust toolchain ------------------------------------------------------
if ! command -v cargo >/dev/null 2>&1; then
  if [[ -x "$HOME/.cargo/bin/cargo" ]]; then
    say "using existing toolchain at ~/.cargo/bin"
  else
    say "cargo not found; installing Rust via rustup (stable, no prompts)"
    command -v curl >/dev/null 2>&1 || die "curl is required to fetch rustup"
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
      | sh -s -- -y --default-toolchain stable --profile minimal
  fi
  # shellcheck disable=SC1091
  source "$HOME/.cargo/env"
fi

command -v cargo >/dev/null 2>&1 || die "cargo still not on PATH; source ~/.cargo/env and re-run"
say "cargo: $(cargo --version)"

# --- 3. Build ---------------------------------------------------------------
say "building release binary"
cargo build --release --manifest-path "$PROJECT_DIR/Cargo.toml"

BIN="$PROJECT_DIR/target/release/cordia-ops"
[[ -x "$BIN" ]] || die "build finished but $BIN is missing"
say "built: $BIN"

# --- 4. Optional install ----------------------------------------------------
if [[ "$DO_INSTALL" == "1" ]]; then
  say "installing to $INSTALL_PATH"
  if [[ -w "$(dirname "$INSTALL_PATH")" ]]; then
    install -m 0755 "$BIN" "$INSTALL_PATH"
  else
    sudo install -m 0755 "$BIN" "$INSTALL_PATH"
  fi
  say "installed. run: cordia-ops you@cordiacode.com"
else
  say "run it with: $BIN you@cordiacode.com"
  say "re-run with --install to place it at $INSTALL_PATH"
fi
