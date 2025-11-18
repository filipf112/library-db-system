-- Uzupełnienie lat dla książek w Filii 2 (Krzyki)
UPDATE KSIAZKI SET rok_wydania = 1886 WHERE id_ksiazki = 2001; -- Potop
UPDATE KSIAZKI SET rok_wydania = 1884 WHERE id_ksiazki = 2002; -- Ogniem i Mieczem
UPDATE KSIAZKI SET rok_wydania = 2022 WHERE id_ksiazki = 5000; -- Harry Potter

COMMIT;