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

## Résultats et scores historiques

Appliquer également **`sql/migrations/20261003_fantasy_results.sql`**. Cette
migration additive et réexécutable ajoute les snapshots de résultats, le barème
figé de la saison, le suivi des parties calculées et les contributions des managers.
Elle autorise aussi le diagnostic des imports de résultats dans `sync_job`.
Elle ne modifie ni les rosters ni les scores existants.

Parcours après rechargement des extensions et synchronisation des commandes :

1. Un administrateur lance
   `/fantasy_import_results debut:2026-08-01 fin:2026-08-08`.
   Les dates sont UTC, début inclus et fin exclue, sur 31 jours maximum dans une
   même année. Le CSV annuel correspond à l'année demandée, sauf surcharge par
   `FANTASY_OE_DATA_URL`. Aucun import de résultats automatique n'est activé.
2. Le propriétaire de la ligue lance `/fantasy calculate league_id:1`.
   Un lot traite au maximum 200 nouvelles parties ; la réponse indique s'il faut
   relancer. Un second calcul sans nouvelle partie ne change rien.
3. Les membres consultent `/fantasy standings league_id:1` et
   `/fantasy scores league_id:1 page:1`. Les réponses sont privées.

### Validation des données

L'adaptateur cible le CSV moderne : `gameid`, `league`, `date` avec heure,
`datacompleteness=complete`, `side`, `position`, `playername`, `teamname`,
`gamelength` **en secondes entières**, `result`, `kills`, `deaths`, `assists`,
`total cs`, `triplekills`, `quadrakills`, `pentakills`, `barons`, `dragons`, `towers`
et `firstblood`. Les identifiants `playerid` et `teamid` utilisent les mêmes règles
de résolution que le pool Oracle's Elixir. Une date sans fuseau est interprétée
en UTC ; une date sans heure est refusée. Le format historique aux anciens noms
de colonnes et durées en minutes n'est pas pris en charge.

Le [dictionnaire Oracle's Elixir](https://lol.timsevenhuysen.com/matchdata/match-data-dictionary/)
décrit les concepts ; il présente aussi des anciens formats. L'auteur signale
les changements de colonnes dans ses
[notes de format](https://www.patreon.com/oracleselixir/posts/downloadable-59096881).
La compatibilité du CSV réel courant reste à vérifier lors du premier import réussi.

Chaque partie doit contenir exactement dix joueurs distincts et deux équipes,
cinq rôles par côté, un vainqueur, une date et une durée cohérentes. Une valeur
vide, négative, non entière ou non finie ne devient jamais zéro. Une partie
incomplète, dupliquée, future ou encore en cours bloque tout le lot. Une fenêtre
vide est signalée sans rafraîchir le succès. Au maximum 1000 parties par import.

Le worker et le verrou PostgreSQL des synchronisations sont partagés avec le
pool et le calendrier. Les écritures du lot sont atomiques. Les identifiants de
partie incluent le championnat et l'année. Les statistiques utilisées pour le
scoring sont conservées dans un snapshot canonique avec empreinte SHA-256.
Réimporter le même contenu est sans effet ; un contenu modifié est refusé sans
écraser les anciens résultats. La correction contrôlée de résultats reste à
implémenter. Aucun rapprochement approximatif avec le calendrier n'est effectué.

Les identités absentes du pool sont créées **inactives**, sans affectation
professionnelle courante. Les données historiques ne changent donc ni l'activité,
ni le rôle, ni le nom, ni l'équipe actuels des joueurs connus. Seuls les mêmes
identifiants externes relient un résultat à un joueur déjà drafté : pas de fusion
approximative par pseudo entre les sources.

### Attribution et classement

Le calcul utilise le barème JSON de `season.scoring_rule_version`, validé et figé
au premier calcul. Modifier cette version ou ses coefficients bloque les calculs
suivants ; les scores publiés ne sont pas recalculés à la consultation.

Le barème existant `riot_classic_v1` reste inchangé : joueur = 2×kills − 0,5×morts
+ 1,5×assists + 0,01×CS + 2×triples + 5×quadras + 10×pentas ; un bonus unique de
2 points si kills **ou** assists atteignent 10. Équipe = 2×victoire + 2×barons
+ dragons + tours + 2×first blood + 2 si victoire en **moins de** 1800 secondes.
Les points sont arrondis à trois décimales, y compris les scores négatifs.

Seules les parties débutant dans `[season.starts_at, season.ends_at[` sont
retenues (pas de borne finale si elle est absente). Le roster est lu à l'heure
de début de chaque partie, sur `[valid_from, valid_until[`. À l'instant exact
d'un transfert, le nouveau propriétaire reçoit les points. Le banc ne marque
pas ; un transfert ultérieur ne déplace pas des points déjà attribués. Les
historiques se chevauchant provoquent un rollback plutôt qu'un double comptage.
La contribution conserve manager, slot, actif, nom, points, version du barème et
référence d'historique. Les remplacements et les calculs partagent le verrou de ligue.

Le classement est une **somme provisoire des contributions importées**, avec
ex æquo sur les points. Il affiche les parties calculées et celles encore en
attente ; il ne garantit pas la complétude des sources. Les managers sans
contribution apparaissent à zéro. Ce classement ne représente pas les victoires
des confrontations. Le mode `normalized` est explicitement refusé en attendant
sa définition, sans lui substituer le mode classique.

## Confrontations et classement en victoires/défaites

Ce module réutilise `matchup` et `manager_period_score` du schéma initial ainsi
que les contributions de la migration `20261003_fantasy_results.sql` : **aucune
migration supplémentaire**. Recharger `cogs.fantasy_lol` et synchroniser les
commandes Discord pour exposer les quatre nouvelles sous-commandes.

1. Après la draft, le propriétaire lance
   `/fantasy fixtures league_id:1 debut:2026-10-05 jours:7` (choisir une date
   future). Un cycle fait rencontrer chaque paire de managers une fois.
   L'ordre suit les positions de draft, puis les identifiants. Avec un nombre
   impair de managers, chacun reçoit exactement une exemption sur le cycle.
2. `/fantasy matchups league_id:1 tour:1` affiche les adversaires et scores.
   Sans `tour`, la commande choisit le tour courant ou le prochain, puis le
   dernier si le calendrier est terminé. Tous les membres de la ligue peuvent
   consulter les confrontations ; les réponses restent privées.
3. Après la fin d'un tour, importer les résultats et lancer `/fantasy calculate`.
   Le propriétaire vérifie leur complétude, puis lance
   `/fantasy round league_id:1 tour:1 action:Clôturer confirmer_complet:True`.
4. `/fantasy ranking league_id:1` affiche les victoires, nuls, défaites et
   exemptions des **seuls tours clôturés**. `/fantasy standings` conserve son
   rôle distinct : somme provisoire des contributions de toute la saison.

Les périodes durent de 1 à 28 jours calendaires, sept par défaut. Leurs bornes
sont à minuit **Europe/Paris**, converties en UTC pour PostgreSQL. Une semaine
du changement d'heure dure donc 167 ou 169 heures. Le début est inclus et la fin
exclue ; chaque partie est rattachée selon son heure de début, sans double
comptage à la frontière. Le premier tour doit commencer dans le futur et après
le début de saison ; le cycle ne doit pas dépasser une fin de saison renseignée.

Répéter la création avec les mêmes paramètres est sans effet. Un calendrier
existant ne peut pas être écrasé ou décalé ; les tours sont insérés ensemble
dans une transaction sous le verrou de ligue. Cette version crée un cycle
simple, sans matchs retour ni playoffs.

### Clôture et imports tardifs

Les scores ouverts proviennent des contributions historiques déjà calculées.
Ils restent provisoires, y compris après la date de fin du tour. La clôture
requiert la fin de période, le calcul de toutes les parties importées de cette
période et l'attestation explicite du propriétaire. Le nombre de parties
importées ne prouve pas à lui seul que la source est complète. Une période
réellement sans partie peut être clôturée à zéro après cette même vérification.
Une égalité à zéro compte alors comme un nul, sauf exemption.

La clôture enregistre ensemble les scores des participants dans
`manager_period_score`. La présence de l'ensemble de ces lignes signifie
« clôturé » ; leur absence signifie « ouvert ». Une clôture partielle incohérente
est refusée. Les calculs, changements de roster, créations et clôtures partagent
le verrou de ligue ; la clôture prend aussi le verrou de l'import des résultats.
Une double clôture ne crée pas de victoire supplémentaire. La lecture utilise
un snapshot PostgreSQL cohérent et ne modifie aucun résultat.

Si de nouvelles parties sont importées dans une période clôturée, ses scores
restent figés, et `/fantasy matchups` ainsi que `/fantasy ranking` signalent les
résultats en attente. Le calcul les refuse jusqu'à la réouverture du tour :

1. `/fantasy round league_id:1 tour:1 action:Réouvrir` ;
2. `/fantasy calculate league_id:1` (relancer si plusieurs lots sont nécessaires) ;
3. revérifier la complétude, puis clôturer de nouveau.

La réouverture retire les résultats de ce tour du classement en attendant sa
nouvelle clôture. Elle conserve les contributions historiques et le calendrier.
Elle ne permet pas de corriger les statistiques d'une partie déjà importée :
ce parcours de correction reste à implémenter. Aucun tour n'est clôturé
automatiquement et aucune notification n'est envoyée aux managers.

### Règles du classement

- Victoire : 3 points ; nul : 1 point ; défaite : 0 point.
- Exemption : comptée séparément, sans victoire ni points de classement.
  Ses contributions ne gonflent ni les points marqués ni la différence du
  classement des confrontations ; elles restent dans le total de saison.
- Départage : points de classement, puis différence points marqués − encaissés,
  puis points marqués. Si ces trois critères sont égaux, rang partagé ; l'ordre
  des identifiants ne sert qu'à stabiliser l'affichage des ex æquo.
- Le mode `normalized` reste refusé tant que ses règles ne sont pas définies.

## Prochaines étapes

1. Rétablir/valider l'accès aux providers réels, puis activer les synchronisations
   et observer leur fraîcheur ainsi que la latence du bot en production.
2. Valider les parcours de marché et d'échange sur le bot déployé.
3. Valider l'import de résultats sur un CSV réel et prévoir la correction
   contrôlée des résultats déjà figés.
4. Valider les confrontations sur Discord, puis définir et implémenter le mode
   normalisé ; étendre les cycles/playoffs si nécessaire.

Le déploiement Discord et la validation des sources réelles restent distincts
des tests automatisés ; ce changement ne déploie pas le bot.
