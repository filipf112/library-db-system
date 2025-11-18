-- Uzupełnienie lat dla książek w Filii 1 (Centrum)
UPDATE KSIAZKI SET rok_wydania = 2021 WHERE id_ksiazki = 100;  -- Fraszki
UPDATE KSIAZKI SET rok_wydania = 2014 WHERE id_ksiazki = 1002; -- Księgi Jakubowe
UPDATE KSIAZKI SET rok_wydania = 1834 WHERE id_ksiazki = 1001; -- Pan Tadeusz

COMMIT;