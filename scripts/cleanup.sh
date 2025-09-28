#!/bin/sh

auxFiles=$(ls | grep -E '\.aux$|\.log$|\.out$|\.toc$|\.idx$|\.ilg$|\.ind$|\.sxc$')
for file in $auxFiles; do
    rm -f "$file"
done

# Remove the package from ~/texmf/tex/latex
if [ -d ~/texmf/tex/latex/zubuvzpevnik ]; then
    rm -r ~/texmf/tex/latex/zubuvzpevnik
fi
