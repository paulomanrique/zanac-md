#!/usr/bin/env bash
set -euo pipefail

# One-time SGDK setup for macOS (Homebrew + ~/SGDK + helper tools).
# Output ROM path is unchanged: zanac-md/out/rom.bin

export PATH="/opt/homebrew/bin:$PATH"

echo "==> Homebrew packages"
brew install openjdk m68k-elf-gcc make texinfo wget gnu-sed

GDK="${GDK:-$HOME/SGDK}"
MARSBIN="$HOME/mars/m68k-elf/bin"
mkdir -p "$MARSBIN"

if [ ! -d "$GDK/.git" ]; then
  echo "==> Cloning SGDK to $GDK"
  git clone --depth 1 https://github.com/Stephane-D/SGDK.git "$GDK"
fi

# shellcheck source=/dev/null
source "$(dirname "$0")/env_mac.sh"

if [ ! -x "$MARSBIN/sjasm" ]; then
  echo "==> Building sjasm"
  rm -rf /tmp/sjasm-build
  git clone --depth 1 --branch v0.39 https://github.com/konamiman/sjasm /tmp/sjasm-build
  make -C /tmp/sjasm-build/Sjasm
  cp /tmp/sjasm-build/Sjasm/sjasm "$MARSBIN/sjasm"
fi

if [ ! -x "$MARSBIN/bintos" ]; then
  echo "==> Building bintos"
  gcc "$GDK/tools/bintos/src/bintos.c" -o "$MARSBIN/bintos"
fi

if [ ! -x "$MARSBIN/convsym" ]; then
  echo "==> Building convsym"
  make -C "$GDK/tools/convsym"
  cp "$GDK/tools/convsym/build/convsym" "$MARSBIN/convsym"
fi

echo "==> Building SGDK libmd.a"
cd "$GDK"
make -f makelib.gen

echo
echo "Setup complete."
echo "  export GDK=$GDK"
echo "  source $(dirname "$0")/env_mac.sh"
echo "  $(dirname "$0")/build.sh"
