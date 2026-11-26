# Pronostics Worlds 2026

Le cog `cogs/worlds2026.py` est chargé automatiquement par `main.py`. Il utilise
ses propres tables `worlds26_*` dans PostgreSQL via `API_SQL`, sans modifier les
anciens pronostics. Les participants, paris, résultats et opérations administratives
sont persistants et isolés par serveur Discord. Aucune mise d'argent.

## Barème

| Format | Mauvais vainqueur | Bon vainqueur, score inexact | Score exact |
| --- | ---: | ---: | ---: |
| BO1 | 0 | — | 1 |
| BO3 / BO5 | 0 | 1 | 3 au total |

Exemple BO5 : résultat G2 3–1 T1 ; pari 3–1 = 3 points, pari 3–0 = 1,
pari 1–3 = 0. Les scores impossibles et égalités sont refusés.
Le classement est recalculé depuis les résultats, sans incrément cumulatif :
relancer l'import n'ajoute jamais deux fois des points. Les ex æquo partagent le rang.
Les matchs annulés, forfaits et résultats en litige ne rapportent aucun point.

## Mise en route

1. Déployer la branche, puis redémarrer le bot (ou recharger `cogs.worlds2026`).
   `API_SQL` doit désigner PostgreSQL ; son utilisateur doit pouvoir créer les
   tables/index. Le premier démarrage crée le schéma de façon additive. Les
   dépendances de production existantes suffisent (SQLAlchemy, aiohttp, interactions.py).
   Pour une installation multi-processus, effectuer ce premier démarrage avec
   une seule instance afin de ne pas faire concourir la création du schéma.
2. Configurer au moins une seconde source pour bénéficier du secours automatique
   indépendant. Sans clés, seule Leaguepedia est interrogée ; la saisie manuelle
   reste disponible si elle échoue. Aucune clé n'est embarquée dans le dépôt.
3. Avec la permission **Gérer le serveur**, lancer `/worlds_admin activer actif:True`
   puis `/worlds_admin synchroniser` et `/worlds_admin statut`.
4. Vérifier `/worlds matchs tous:True`, les adversaires, BO et heures. Les dates
   Discord s'affichent dans le fuseau du lecteur. Aucun pari rétroactif n'est accepté.
5. Les membres utilisent `/worlds inscription`, puis `/worlds parier`.

### Sources et configuration

| Source | Variables d'environnement | Périmètre |
| --- | --- | --- |
| Leaguepedia | aucune | `MatchSchedule`, page `2026 Season World Championship` et sous-pages |
| LoL Esports | `WORLDS_LOLESPORTS_API_KEY` | ligue de slug `worlds`, calendrier du site, octobre–novembre 2026 |
| PandaScore | `WORLDS_PANDASCORE_TOKEN`, `WORLDS_PANDASCORE_SERIE_IDS` | identifiants numériques des séries Worlds 2026, séparés par des virgules |

La clé LoL Esports est celle de son API de calendrier, **pas la clé Riot Developer
utilisée pour les matchs de joueurs**. Cette API de site n'a pas de contrat public
de stabilité ; l'exploitant doit disposer d'une clé valide. PandaScore requiert
un compte/jeton autorisant les données de calendrier/résultats et les IDs exacts
des séries du tournoi. Vérifier les IDs dans la réponse `/lol/series` ou le portail
PandaScore avant de les configurer. Ne pas utiliser les IDs des tournois à leur place.

Les sources configurées sont toutes consultées : une réponse partielle ou en retard
de la première n'empêche pas la suivante d'apporter un match ou résultat. Les
équipes et scores sont remis dans un ordre stable, avec correspondance explicite
des noms courants/sponsors. Aucun résultat n'est déduit d'un score intermédiaire.

Un passage normal a lieu toutes les dix minutes, une collecte commune à tous les
serveurs activés. Le diagnostic manuel respecte le même délai. Après échec, délai
de 20, 40 puis 60 minutes entre tentatives de cette source ; les autres continuent.
Chaque requête expire après 20 secondes, chaque source après 90 secondes ; pagination
bornée à 10 pages Leaguepedia/PandaScore et 12 LoL Esports. Les jetons sont passés
dans les en-têtes et ne sont pas inclus dans les diagnostics utilisateurs.

L'automatisation est active d'octobre à fin novembre 2026, y compris le rattrapage
après la finale. La synchronisation manuelle reste possible ensuite. Désactiver
le serveur arrête ses nouveaux paris/imports, sans supprimer son historique.

Diagnostic réseau sans base ni Discord :

```console
python -m scripts.check_worlds2026_sources
```

Un HTTP 200 contenant une erreur Cargo, une réponse vide, un schéma invalide,
une pagination incomplète ou un timeout est signalé comme un échec. Les anciennes
données sont conservées. Les lignes incomplètes (TBD, heure absente, BO inconnu,
score incohérent) sont ignorées et comptabilisées dans le statut de la source.
Le diagnostic indique l'heure du dernier succès, distincte de la dernière tentative.

## Commandes membres

| Commande | Utilité |
| --- | --- |
| `/worlds regles` | Règles et barème |
| `/worlds inscription` | S'inscrire ou réactiver sa participation |
| `/worlds retrait` | Suspendre sa participation, conserver points et historique |
| `/worlds participants` | Participants du serveur |
| `/worlds equipes` | Équipes connues dans le calendrier importé |
| `/worlds matchs [tous]` | Matchs, ID, heure, fermeture, BO, résultats et source |
| `/worlds parier match_id score1 score2` | Enregistrer ou remplacer son pronostic |
| `/worlds mes_pronos` | Historique personnel et points, en privé |
| `/worlds classement` | Classement public du serveur |

Le score suit **l'ordre affiché dans `/worlds matchs`**, qui peut différer de
l'ordre des équipes saisi lors d'un ajout manuel. Les vues longues sont paginées.
Toutes les réponses sauf le classement sont privées. Aucun pronostic d'autrui
n'est exposé par une commande membre.

## Administration et incidents

Les commandes `/worlds_admin` exigent **Gérer le serveur**, vérifié à chaque
exécution côté bot. Les MP sont refusés. Les opérations sont auditées avec
l'identifiant de l'administrateur et la date.

- `activer actif` : activer/désactiver inscriptions et imports du serveur.
- `synchroniser` : lancer une collecte sous réserve du délai anti-spam.
- `statut` : derniers succès/échecs, connecteurs non configurés, anomalies et audit récent.
- `ajouter equipe1 equipe2 debut bo` : calendrier manuel, par exemple début
  `2026-10-23T19:00:00+02:00`. Le fuseau est obligatoire.
- `horaire match_id debut` : rectifier l'heure ; une fermeture ne peut jamais
  être repoussée. Un match reprogrammé plus tard garde sa première limite de paris.
- `resultat match_id score1 score2 raison` : valider ou corriger un score après
  la fermeture. Les points sont recalculés ; cette décision est protégée contre
  les écrasements automatiques ultérieurs.
- `annuler match_id raison` : neutraliser un match, conserver ses pronostics/audit.
- `associer match_id source identifiant` : rattacher explicitement un ID fournisseur
  à un match déjà présent lorsque l'heure a trop changé ou le rapprochement est ambigu.

Les identifiants fournisseur sont mémorisés. Un autre fournisseur est rapproché
par paire d'équipes et horaire à moins de 12 heures, seulement si le candidat est
unique ; deux IDs différents d'une même source ne sont jamais fusionnés implicitement.
Un nouveau résultat contradictoire suspend les points du match jusqu'à une
validation `resultat`. Une source en retard ne rouvre jamais les paris et n'efface
jamais un résultat. Un changement d'adversaires ou de BO met le match en litige :
annuler l'ancien puis ajouter le match correct, pour ne pas réutiliser des paris
portant sur une autre confrontation. En cas de rematch ambigu, utiliser `associer`.

Les écritures sont sérialisées par un verrou SQL commun, y compris entre processus.
L'heure limite est contrôlée **après** acquisition de ce verrou. Si un fournisseur
révèle après coup un début plus tôt, les pronostics déposés après cette limite ne
rapportent aucun point. Une panne totale des sources ne permet pas de parier après
la date connue ; le résultat reste simplement en attente.

## Validation avant ouverture aux joueurs

1. `python -m pytest -q tests/test_worlds2026.py` : règles, imports, panne/reprise,
   identités, verrouillage, isolation, commandes Discord réelles et pagination.
2. Dans une base **de test**, définir `WORLDS_TEST_DATABASE_URL`, puis
   `python -m pytest -q tests/test_worlds2026_postgres.py`. Le compte doit pouvoir
   créer un schéma temporaire. Vérifie les écritures concurrentes et le verrouillage.
   La CI exécute ces tests avec PostgreSQL 16 et les tests hors ligne sous Windows.
3. Exécuter le diagnostic des sources depuis la machine du bot. Ne pas annoncer
   le secours automatique opérationnel tant que deux sources indépendantes n'ont
   pas été validées en direct avec la configuration de déploiement.
4. Sur un serveur Discord de test, activer, synchroniser et confronter un match
   au calendrier officiel. Tester inscription et remplacement d'un pari,
   classement, résultat/correction/annulation et refus avec un compte sans permission.
5. Redémarrer : vérifier inscriptions, paris, fermeture et absence de double point.
   Enfin activer sur le serveur cible.

Les tests hors ligne utilisent des réponses représentatives, pas une garantie que
les fournisseurs resteront disponibles. Les tests et une PR verte ne constituent
pas un déploiement ni une validation réelle dans Discord.

## Références des contrats de données

- [Riot — Worlds 2026 Primer](https://lolesports.com/en-GB/news/worlds-2026-primer) : formats et fenêtre de compétition.
- [Leaguepedia — déclaration MatchSchedule](https://lol.fandom.com/wiki/Module:CargoDeclare/MatchSchedule) : MatchId, BestOf, HasTime, scores et annulation.
- [PandaScore — liste des matchs LoL](https://developers.pandascore.co/reference/get_lol_matches) et [prise en main](https://developers.pandascore.co/docs/getting-started).
