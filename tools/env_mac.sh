# Source before building on macOS:
#   source tools/env_mac.sh
#
# SGDK: ~/SGDK (clone of https://github.com/Stephane-D/SGDK)
# Tools: ~/mars/m68k-elf/bin (sjasm, bintos, convsym)

export GDK="${GDK:-$HOME/SGDK}"
export PATH="$HOME/mars/m68k-elf/bin:/opt/homebrew/opt/openjdk/bin:/opt/homebrew/opt/make/libexec/gnubin:/opt/homebrew/bin:$PATH"
