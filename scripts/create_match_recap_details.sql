-- Données persistantes des boutons Détail du score et Différentiel d'or.
CREATE TABLE IF NOT EXISTS match_recap_details (
    match_id TEXT NOT NULL,
    joueur BIGINT NOT NULL,
    data JSONB NOT NULL,
    PRIMARY KEY (match_id, joueur)
);
