#!/bin/sh

auxFiles=$(find . | grep -Ev '.git/' | grep -E '\.aux$|\.log$|\.out$|\.toc$|\.idx$|\.ilg$|\.ind$|\.sxc$|\.sbx$|\.sxd$|\.fls$|\.fdb_latexmk$|\.aut$|/tmp-ly$')
for file in $auxFiles; do
    rm -rf "$file"
done

# Remove the package from ~/texmf/tex/latex
if [ -d ~/texmf/tex/latex/zubuvzpevnik ]; then
    rm -r ~/texmf/tex/latex/zubuvzpevnik
fi
