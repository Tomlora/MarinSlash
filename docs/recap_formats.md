# Formats du récapitulatif LoL

Le format est choisi individuellement pour chaque compte suivi avec la colonne
`tracker.recap_format`.

Valeurs acceptées :

- `legacy` : rendu historique, valeur par défaut ;
- `modern` : nouveau tableau de bord sombre.

## Installation

Exécuter une fois :

```sql
\i migrations/20260711_add_recap_format.sql
```

Ou exécuter directement le contenu du fichier dans PostgreSQL.

## Activer le nouveau rendu

Par PUUID :

```sql
UPDATE tracker
SET recap_format = 'modern'
WHERE puuid = '<PUUID>';
```

Par Riot ID et tag :

```sql
UPDATE tracker
SET recap_format = 'modern'
WHERE riot_id = 'tomlora'
  AND UPPER(riot_tagline) = 'EUW';
```

Retour à l'ancien rendu :

```sql
UPDATE tracker
SET recap_format = 'legacy'
WHERE puuid = '<PUUID>';
```

## Compatibilité

Tant que la migration n'est pas appliquée, le code retombe automatiquement sur
`legacy`. Une erreur pendant le rendu moderne déclenche également le rendu
historique.

Le format moderne est activé pour `RANKED`, `FLEX`, `NORMAL` et `SWIFTPLAY`.
`ARAM` et `CLASH ARAM` restent temporairement sur le format historique, car ce
rendu contient encore la logique métier de classement ARAM.
