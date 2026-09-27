-- À exécuter une fois si le compte utilisé par le bot ne peut pas créer de tables.
-- Le code applique également ce CREATE TABLE automatiquement lorsque c'est autorisé.
-- Une entrée représente les records d'un joueur sur un match, au moment du récap.
CREATE TABLE IF NOT EXISTS match_records (
    match_id VARCHAR(40) NOT NULL,
    joueur BIGINT NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (match_id, joueur)
);

CREATE INDEX IF NOT EXISTS idx_match_records_joueur
    ON match_records (joueur, created_at DESC);
