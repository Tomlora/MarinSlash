# Fantasy LoL — état de la branche fantasyleague

Le module est en développement dans la PR #26. Ce document décrit le code du
dépôt ; il ne remplace pas le README externe `Marin_Fantasy_LoL_README.md`, qui
n'a pas pu être consulté lors de cette reprise.

## Après la draft

- `/fantasy roster league_id:1` affiche ton roster de la saison courante,
  les identifiants des joueurs, leurs rôles et les championnats verrouillés.
- `/fantasy lineup league_id:1 joueur_id:6` titularise un joueur de ton banc
  au rôle enregistré dans le pool. Le titulaire précédent rejoint le banc.
- Le roster conserve cinq titulaires, trois remplaçants et une équipe ; les
  titulaires doivent représenter au moins deux championnats.
- Le championnat du joueur entrant **et** celui du sortant doivent être libres.
  Un match programmé, en cours ou terminé verrouille son championnat pendant
  toute sa date Europe/Paris. Un match annulé ou reporté ne le verrouille pas.
- Un joueur devenu inactif reste visible et peut être sorti du cinq titulaire,
  mais ne peut pas être titularisé. Son dernier championnat connu sert au lock.
- Seul le manager concerné peut changer son roster, sur le serveur de sa ligue,
  lorsque celle-ci est active. Les réponses sont privées.

Les changements et les deux intervalles d'historique sont écrits dans une seule
transaction. Une erreur annule tout. Un verrou de ligue sérialise les demandes
concurrentes ; des verrous PostgreSQL protègent les données du pool et du calendrier
pendant la validation. Les deux nouvelles commandes exécutent le SQL dans un
thread après avoir accusé réception de l'interaction Discord.

## Installation et vérification

Appliquer d'abord le schéma initial `sql/migrations/20260725_fantasy_initial.sql`,
puis la migration additive et réexécutable `sql/migrations/20261002_fantasy_sync.sql`.
Elle ajoute les états des synchronisations et la couverture du calendrier, sans
modifier les rosters existants. Recharger `cogs.fantasy_admin` et `cogs.fantasy_lol`,
puis synchroniser les commandes Discord.

Les locks reposent sur le calendrier enregistré. Un remplacement est refusé si
le calendrier d'un des deux joueurs n'a pas été vérifié depuis trois heures,
ou si sa fenêtre ne couvre pas toute la journée de Paris. Un championnat absent
de la réponse n'est pas considéré comme vérifié, même si d'autres championnats
ont été importés. Cela peut également bloquer les remplacements hors saison :
l'absence de matchs ne prouve pas à elle seule que le provider est complet.

## Agents libres et échanges

Le marché ouvre après la draft, lorsque la ligue est active. Les opérations
utilisent les tables du schéma initial : aucune migration supplémentaire après
`20261002_fantasy_sync.sql` n'est nécessaire pour ce module.

- `/fantasy market league_id:1 type:Joueur` liste les joueurs libres de la saison,
  avec filtres de rôle et de championnat et pagination de 20 résultats.
  Le type Équipe liste les équipes professionnelles libres.
- `/fantasy claim league_id:1 type:Joueur libere_id:6 recrute_id:90` remplace un
  joueur possédé par un joueur libre. Le recrutement et la libération sont
  indissociables, sans période de waivers ni budget d'enchères. La première
  transaction validée obtient le joueur si plusieurs managers le demandent.
- `/fantasy roster league_id:1 manager:@AutreManager` permet à un membre de la
  ligue de consulter les identifiants du roster d'un autre membre.
- `/fantasy trade_offer league_id:1 type:Joueur manager:@AutreManager offert_id:6 demande_id:16`
  crée une offre persistante à un contre un. Les équipes peuvent être échangées
  entre elles ; les échanges joueur contre équipe ou à plusieurs assets ne sont
  pas pris en charge. Les assets restent détenus par leurs managers jusqu'à
  l'acceptation ; une offre ne les réserve pas.
- `/fantasy trades league_id:1` affiche les offres envoyées/reçues, puis les
  échanges terminés, par pages de 10. Les réponses sont privées ; aucun DM
  automatique n'est envoyé au destinataire.
- `/fantasy trade_reply league_id:1 trade_id:1 action:Accepter` valide une offre
  reçue. Seul son destinataire peut l'accepter ou la refuser ; seul son auteur
  peut l'annuler. Refus et annulation restent possibles si le calendrier devient
  périmé ou si la ligue n'est plus active.

L'asset reçu occupe la place de l'asset cédé : un recrutement à la place d'un
titulaire doit donc correspondre à son rôle. Un joueur reçu à la place d'un
remplaçant reste sur le banc. Le roster complet et la diversité des championnats
sont validés pour **les deux managers**, sans réorganisation automatique.

Les championnats de tous les assets transférés doivent être déverrouillés et
leurs calendriers vérifiés. L'activité, la propriété et les règles du roster sont
revérifiées à l'acceptation. Les offres concurrentes impliquant un asset libéré
ou transféré sont invalidées, même s'il est recruté de nouveau ultérieurement.

Les écritures de propriété, d'historique et d'état d'échange partagent une seule
transaction. Le verrou de ligue est commun à la draft, aux remplacements et au
marché ; deux recrutements ou acceptations simultanés ne peuvent pas transférer
deux fois le même asset. Les commandes accusent réception avant le travail SQL,
exécuté hors de la boucle Discord.

## Synchronisations automatiques

L'activation se fait avec `FANTASY_AUTO_SYNC_ENABLED=1`, après application de la
migration et validation des sources. Par défaut, elle reste désactivée. Les
commandes manuelles `/fantasy_update_db` et `/fantasy_update_schedule` restent
utilisables et passent par le même worker.

Quand l'automatisation est active et qu'une ligue est en inscription, draft ou
active, une boucle vérifie toutes les quinze minutes si un import est dû :

- calendrier : une heure entre deux tentatives ;
- pool Oracle's Elixir : 24 heures après une tentative réussie, six heures après
  un échec ; la fréquence est conservée en PostgreSQL après redémarrage ;
- fenêtre calendrier : deux jours dans le passé et 21 jours dans le futur ;
- fallback LoL Esports : une requête `getLeagues` et au plus six pages de calendrier,
  dans les deux directions ; une fenêtre tronquée est refusée.

`/fantasy_sync_status` indique l'activation, les dernières tentatives, les derniers
succès, les types d'erreurs et les championnats non vérifiés. Un succès partiel ne
rafraîchit que les championnats effectivement présents dans l'import.

Un worker unique exécute HTTP, parsing et SQL hors de la boucle Discord. Un verrou
PostgreSQL empêche également deux processus du bot de synchroniser simultanément.
Une demande concurrente est refusée plutôt que mise en file. Annuler une interaction
ou décharger l'extension arrête l'attente/la planification, mais n'interrompt pas
les écritures déjà parties dans le worker ; le verrou reste détenu jusqu'à sa fin.
Les téléchargements ont des timeouts, le job utilise un timeout asyncio de cinq
minutes et les écritures limitent chaque attente de verrou à cinq secondes et
chaque instruction SQL à trente secondes. Le timeout asyncio n'interrompt pas un
appel Python/SQL synchrone en cours ; ce n'est donc pas une limite stricte de durée
murale. La charge CPU et la latence du bot restent à observer en production.

Les erreurs et les réponses vides ne rafraîchissent pas le calendrier. Les imports
conservent les identifiants existants, les matchs terminés et leurs liens ; un
match programmé absent du nouveau calendrier est marqué annulé au lieu d'être
supprimé.

### Vérification réelle du 2 octobre 2026

La requête Cargo Leaguepedia a répondu `ratelimited`. L'ancienne URL Oracle's Elixir
visant `s3.us-west-2.amazonaws.com` a répondu HTTP 301 avec une indication de région
`us-east-1`. Le nom S3 canonique désormais configuré a répondu HTTP 403 pour le CSV
2026. Aucune collecte réelle complète n'est donc validée. `FANTASY_OE_DATA_URL`
permet de fournir une URL autorisée et fonctionnelle ; le code ne contourne pas
le refus d'accès. Les tests des providers reposent sur des fixtures. Le fallback
LoL Esports n'a pas été sollicité pendant cette vérification réseau.

```bash
python -m unittest discover -s tests -p 'test_fantasy*.py' -v
```

Sans `FANTASY_TEST_DSN`, les tests PostgreSQL sont explicitement ignorés.
Pour les lancer, fournir une base **jetable** nommée `marin_fantasy_test` : ces
tests réinitialisent son schéma `fantasy`. Ne jamais utiliser une base du bot.
Le workflow `Fantasy tests` crée cette base sur PostgreSQL 16 et utilise
Python 3.10, SQLAlchemy 2.0.4 et interactions.py 5.13.2.

## Prochaines étapes

1. Rétablir/valider l'accès aux providers réels, puis activer les synchronisations
   et observer leur fraîcheur ainsi que la latence du bot en production.
2. Valider les parcours de marché et d'échange sur le bot déployé.
3. Importer les résultats Oracle's Elixir et calculer les scores versionnés en
   utilisant le roster historique au moment des matchs.
4. Relier les périodes de confrontation aux scores, puis exposer le classement.

Le déploiement Discord et la validation des sources réelles restent distincts
des tests automatisés ; ce changement ne déploie pas le bot.
