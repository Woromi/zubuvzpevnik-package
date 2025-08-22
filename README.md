# Zubův zpěvník

V této knihovně jsem si upravil `songs` balíček podle svých potřeb tak, aby vypadal jako můj starý zpěvník, který jsem si psal ve Wordu.

## zubuvzpevnik.pkg

Balíček postavený na základě `songs` balíčku. Jsou v něm definované vlastní styly slok, refrénu a pár dalších vychytávek.

## velkyzpevnik.cls

Používá třídu `zubuvzpevnik`. Nad rámec toho definuje styl velkého A4 zpěvníku. Definuje titulní stranu, obsah.

## taborovyzpevnik.cls

Používá třídu `zubuvzpevnik`. Nad rámec toho definuje styl malého A5 zpěvníku používaného na táboře. Definuje titulní stranu, obsah, konec zpěvníku, číslování stránek. Doplní prázdné stránky tak, aby vycházely do bookletu.
