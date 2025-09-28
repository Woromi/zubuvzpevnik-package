SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

texlua "$SCRIPT_DIR/songidx.lua" -l cs_CZ.utf8 "obsah/${1}.sxd" "obsah/${1}.sbx"
