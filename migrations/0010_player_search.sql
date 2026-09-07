BEGIN;

-- Searching for "jose ramirez" has to find "José Ramírez". The `unaccent` extension
-- would do it, but installing an extension needs privileges a deployment may not have,
-- so the fold is spelled out instead.
--
-- It lives in a function rather than inline so the index and the query cannot drift
-- apart: an index built on one expression is simply not used by a query written with
-- another, and the only symptom would be a search that quietly got slower.
CREATE OR REPLACE FUNCTION fold_name(value TEXT) RETURNS TEXT
    LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
AS $$
    SELECT lower(translate(
        value,
        'áàäâãåéèëêíìïîóòöôõúùüûñçÁÀÄÂÃÅÉÈËÊÍÌÏÎÓÒÖÔÕÚÙÜÛÑÇ',
        'aaaaaaeeeeiiiiooooouuuuncAAAAAAEEEEIIIIOOOOOUUUUNC'
    ))
$$;

-- `text_pattern_ops` so a prefix search can use the index; a substring search still
-- scans, which at league size costs nothing.
CREATE INDEX IF NOT EXISTS idx_players_fold_name
    ON players (fold_name(full_name) text_pattern_ops);

COMMIT;
