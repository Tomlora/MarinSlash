# `/recap` : champion et observation

`riot_id` reste obligatoire. `riot_tag` et `mode` conservent leur comportement.

- `champion` : facultatif, avec autocomplétion depuis les champions déjà connus
  du bot. La recherche ignore la casse, les espaces et la ponctuation (`Kai'Sa`,
  `Kaisa`, `Dr. Mundo`, `DrMundo`). Aucun appel Riot supplémentaire.
- `observation` : **Observation (Durée)**, 24h, 48h, 72h, 96h, Semaine (7 jours),
  Mois (30 jours), Aujourd'hui (depuis minuit à Paris).
- `observation_parties` : **Observation (Nombre de parties)**, de 10 à 100 par pas
  de 10, sans limite d'ancienneté.

Choisir une seule option d'observation. Sans choix, le récap couvre les dernières
24 heures. Fournir les deux renvoie un message explicatif.

Exemples :

```text
/recap riot_id:MonPseudo champion:Ahri observation:48h
/recap riot_id:MonPseudo champion:Ahri mode:Ranked observation_parties:20
```

Le second exemple sélectionne les 20 dernières parties Ranked **avec Ahri**.
Les filtres joueur, tag, mode et champion sont appliqués avant le nombre demandé.
Les doublons d'un même match ne consomment pas de place. Les parties sont affichées
de la plus récente à la plus ancienne et toutes les statistiques portent sur cette
sélection. Si l'historique contient moins de parties, le nombre disponible est indiqué.
Les titres et le message d'absence de résultat rappellent les filtres choisis.

## Validation et mise en service

`python -m pytest -q tests/test_recap_filters.py` vérifie la sélection SQL,
les bornes temporelles (dont les changements d'heure), les doublons, les filtres,
les statistiques et la pagination Discord jusqu'à 100 parties.
La CI exécute aussi ces tests avec PostgreSQL 16 (`RECAP_TEST_DSN`, base jetable).

Après fusion, recharger l'extension et synchroniser les commandes slash selon la
procédure habituelle du bot. Vérifier dans Discord les deux exemples, un champion
sans résultat et les deux observations fournies ensemble. Aucune migration SQL.

Sous Windows, installer aussi la dépendance `tzdata` déclarée dans
`requirements.txt`, dans l'environnement Python du bot. Elle fournit les fuseaux
IANA nécessaires à l'option Aujourd'hui. Pour mettre à jour une installation
existante depuis le dossier du bot :

```powershell
.\.venv\Scripts\python.exe -m pip install tzdata
```

Redémarrer ensuite le bot. Les observations par nombre de parties et durée
glissante sont calculées sans charger Europe/Paris. Les tests dédiés vérifient
Python 3.10 sous Windows et forcent un système sans base de fuseaux IANA.
