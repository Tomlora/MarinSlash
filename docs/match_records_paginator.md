# MatchLoL — aperçu compact et records détaillés

## Affichage public

Après une analyse éligible (RANKED/FLEX/SWIFTPLAY d'au moins 15 min,
ou ARAM d'au moins 10 min), le récap sélectionne au maximum **trois
statistiques marquantes** parmi les catégories activées. Par défaut, leurs
distinctions sont regroupées par statistique (format compact de la PR42).
L'utilisateur peut choisir les sections **Records All-Time**, **Records Saison**
et **Records Perso**, comme l'ancien affichage (format PR43 décrit ci-dessous). Une statistique peut apparaître dans plusieurs sections : chaque
ligne conserve son propre rang, score précédent, détenteur et logo du champion.
Les sections vides sont omises et séparées par une ligne vide.

Les records historiques absolus passent en priorité. Une diversité de
statistiques est recherchée pour les autres places. Le champ public reste
limité à 960 caractères, titres et compteur inclus : si nécessaire, moins
de trois statistiques sont affichées, sans couper une ligne ni retirer un
scope d'une statistique affichée. Le compteur indique le total des données
enregistrées et le nombre de statistiques restantes est annoncé.

Exemple (les médailles et logos sont les emojis natifs du serveur) :

```
🏛️ Records All-Time
⑤ dmg ad max en teamfight → 12536 · ~~12490~~ @Tomlora [logo]
⑧ dmg max en teamfight → 13401 · ~~13364~~ @Tomlora [logo]

👑 Records Saison
⑤ dmg max en teamfight → 13401 · ~~13290~~ @Tomlora [logo]
⑤ dmg ad max en teamfight → 12536 · ~~12490~~ @Tomlora [logo]

4 distinctions · 2 statistiques
```

Le nom de la statistique est en gras, le score en code, et l'ancien score
barré. Les logos proviennent de `data_champion`.

Quand au moins une distinction a été détectée, un bouton **🏆 Voir tous
les records** est attaché au message, sous l'embed et son image. Le bouton
ouvre une **réponse éphémère** ; les autres membres du serveur ne voient
pas les clics ni les pages.

## Pages de détail

- Page d'aperçu : nombre de distinctions et de statistiques distinctes,
  ventilé par All-Time, Saison et Personnel, puis trois temps forts.
- Pages All-Time, Saison, Personnel : cinq distinctions par embed, avec
  position, valeur, ancien record, détenteur précédent et champion.
- Précédent / Suivant, accès direct à la première page de chaque scope et
  Fermer. Les pages sont de vrais embeds et les contrôles sont les boutons
  Discord natifs (pas un panneau flottant ou des onglets HTML).

Le callback du bouton public ainsi que les boutons de pagination utilisent
des IDs déterministes et uniques dans chaque message, y compris pour
les boutons désactivés. Chaque contrôle possède un suffixe propre :
Précédent, Suivant et les raccourcis peuvent viser la même page sans
provoquer `component_custom_id_duplicated`. Les anciens IDs restent reconnus. Les données sont rechargées depuis PostgreSQL à
chaque interaction : le **bouton public reste utilisable après un
redémarrage** du bot. La réponse au clic est acquittée immédiatement,
puis PostgreSQL est interrogé dans un thread séparé. Un délai de huit
secondes et un message d'erreur visible remplacent l'attente infinie en
cas de base indisponible ou d'erreur lors de la construction du paginator.
Les réponses éphémères restent soumises aux durées d'accès imposées
par Discord.

## Sauvegarde et déploiement

La table **match_records** stocke un JSONB par couple
(match_id, joueur), contenant chaque RecordEntry détecté, sans effacer
les distinctions de scope secondaires. Elle enregistre aussi les analyses
sans record. Seuls les matchs analysés avec records activés créent un
snapshot. Les anciennes parties ne sont pas recalculées : la commande
historique indique explicitement l'absence de snapshot.

Le code essaie de créer la table au premier enregistrement. Si le rôle
PostgreSQL n'a pas le droit CREATE, exécuter **scripts/create_match_records.sql**
avant de déployer. En cas d'échec SQL, le récap public reste envoyé, sans
bouton cassé, et l'erreur figure dans les logs.

Le paramètre **tracker.save_records** est respecté par /game et par le
rattrapage /game_rattrapage (une erreur ancienne de type bool.empty est
corrigée dans la même PR).

## Commandes

**/match_records match_id [riot_id] [riot_tag]** — retrouver les
distinctions enregistrées d'un match. Accepte EUW1_123456789 ou le
numéro seul. Si plusieurs comptes suivis ont joué ce match, indique
les noms disponibles et demande de préciser le Riot ID.

**/lol_records_demo [scenario]** — prévisualiser un vrai message Discord
éphémère avec un embed de match fictif, une image de scoreboard générée
localement et le même résumé compact. Aucun accès Riot, aucun match ni
record fictif écrit en base. Le menu permet de changer de situation
sans relancer la commande ; le bouton ouvre les véritables pages de
détail du scénario choisi.

Scénarios disponibles :

| Valeur | Contenu |
| --- | --- |
| none | Aucun record |
| alltime | Un record All-Time |
| personal | Un record personnel |
| season | Un record de saison |
| alltime_personal | Une statistique avec deux distinctions |
| all_scopes | Une statistique avec les trois distinctions |
| tie | Égalisations |
| podium | Podiums sans première place |
| ten | Dix records distincts |
| twenty_five | Vingt-cinq records répartis sur plusieurs pages |
| fifty | Cinquante records sur une pagination longue |
| mixed | Sept statistiques, vingt-et-une distinctions multi-scopes |

La commande /lol_records existe déjà dans le cog des classements :
**/match_records** est un nom distinct pour éviter toute collision.

## Vérifications de recette

1. Lancer /lol_records_demo, choisir « aucun record », puis ouvrir
   le détail : une seule page et aucun bouton Suivant actif.
2. Choisir All-Time + personnel : une seule statistique sélectionnée,
   deux lignes complètes réparties dans les sections All-Time et Perso,
   puis dans leurs pages de détail respectives.
3. Choisir 10, 25 puis 50 records : changer de scope, atteindre
   la dernière page, vérifier les limites de cinq champs par embed.
4. Cliquer sur le bouton d'une véritable partie éligible : le
   récap public n'est pas édité ; la réponse est privée.
5. Redémarrer le bot puis cliquer sur un ancien bouton public
   depuis un message dont le snapshot existe toujours.
6. Désactiver tracker.save_records pour un compte et vérifier
   qu'aucun record ni bouton trompeur n'apparaît dans /game.

## Après une correction du code

Un récap **déjà publié** sur Discord ne se met pas automatiquement à jour :
le nouveau texte compact doit être publié de nouveau. En revanche, les
snapshots `match_records` existants contiennent déjà `old_holder` et
`old_champion` : le bouton de détail sur un ancien message peut être
réutilisé après redémarrage, sans supprimer ni recalculer la partie. Pour
revoir le récap public de la même partie, utiliser la procédure habituelle
de suppression ciblée, puis relancer `/game` après déploiement.


## Préférences personnelles — /settings_records

Chaque utilisateur peut modifier ses propres préférences, sans permission
administrateur et sans pouvoir modifier celles d'un autre membre.

- `/settings_records` : consulter ses réglages (réponse privée).
- `/settings_records format:compact` : présentation compacte par statistique, valeur par défaut.
- `/settings_records format:sections` : présentation en sections par catégorie.
- `/settings_records alltime:true saison:false perso:true` : deux catégories.
- `/settings_records alltime:false saison:false perso:false` : aucune catégorie.
- Les options omises conservent leur valeur. Les trois catégories sont activées
  par défaut. Les huit combinaisons sont prises en charge.

Une nouvelle table `records_preferences`, indexée par identifiant Discord,
évite de dupliquer les réglages entre les comptes Riot d'une même personne.
Elle est créée à la première modification. Si le rôle SQL n'a pas le droit
CREATE, appliquer `scripts/create_records_preferences.sql`.

Les **nouveaux récaps publics** utilisent les réglages du propriétaire du compte
`tracker`. Les **détails privés** et la démo utilisent les réglages de la personne
qui clique. Les catégories sont filtrées avant la sélection des trois statistiques
et la pagination. Sans catégorie, le champ public et son bouton de records sont
masqués ; un ancien bouton reste consultable et explique comment les réactiver.
Les snapshots restent complets, même quand toutes les catégories sont masquées.
L'option existante `tracker.save_records` continue de contrôler le calcul des
records ; ces nouvelles préférences contrôlent uniquement leur présentation.

Un message Discord déjà publié ne change pas automatiquement. Une nouvelle
publication ou le rechargement d'un récap avec snapshot applique les réglages
courants. Les identifiants des anciens boutons restent compatibles.

## Teamfight et Ganks

Sous un récap dont la ligne `matchs` a été sauvegardée, les boutons
**⚔️ Teamfight** (rouge) et **🌿 Ganks** (vert) ouvrent des pages privées :
résumé, puis chronologie avec cinq champs maximum par page.
Précédent, Suivant et Fermer restent disponibles. Les boutons fonctionnent
après redémarrage, même lorsque les records sont masqués, sans appel Riot.

**Teamfight** reprend la lecture de la commande dédiée : bilan des teamfights,
escarmouches, duels et victoires en infériorité ; meilleur teamfight en dégâts
infligés et, si disponible, en dégâts reçus ; chronologie des combats du joueur.
Les dégâts infligés utilisent `damage_frame_window`, comme la commande, et
leur part est calculée sur les participants de la même équipe et du même point
de vue sauvegardé. Les dégâts reçus sont toutes sources. Une valeur absente
reste « — ». Les fenêtres de mesure peuvent se chevaucher.

**Ganks** reprend le résumé des deux junglers, les appuis TOP/MID/BOT, la
qualité de détection et les tentatives chronologiques entre **0:00 et 13:59**.
Le point de vue allié/ennemi vient de l'index Riot du joueur du récap, y compris
côté rouge. Le succès strict exclut les échanges de kills. Les anciennes données
sans issue détaillée affichent « Issue non renseignée », sans déduire un succès
du seul booléen historique. Ranked, Flex et Swiftplay sont pris en charge.
Un mode incompatible, une équipe inconnue ou des tables/données absentes
produisent un message explicite.

Les clics sont acquittés avant les requêtes, exécutées hors de la boucle asyncio
avec un délai maximal de huit secondes. Les erreurs retirent les contrôles
de la vue privée et invitent à rouvrir le bouton du récap.

Les nouveaux récaps affichent les nouveaux boutons. Les messages déjà envoyés
ne sont pas modifiés automatiquement : leurs anciens boutons Analyse et
Progression gardent leur fonctionnement. Aucun changement de schéma requis ;
les deux nouvelles vues lisent les analyses déjà sauvegardées.

## Vérifications supplémentaires

1. Tester les deux formats et les huit combinaisons de catégories.
2. Vérifier avec deux utilisateurs que leurs choix restent indépendants.
3. Masquer tous les records, puis les réactiver : le snapshot doit rester complet.
4. Ouvrir Teamfight et Ganks, atteindre la dernière page, revenir puis fermer.
5. Vérifier un match côté rouge, le seuil 14:00 et les issues de gank anciennes.
6. Tester les données absentes, les colonnes de dégâts reçus manquantes et ARAM.
7. Redémarrer le bot puis utiliser les boutons récents et anciens.
8. La CI vérifie les composants Discord réels hors ligne et les requêtes sur
   une base PostgreSQL jetable `records_test`, sans connexion à la base du bot.

## Détail du score et différentiel d'or

La rangée du récap contient jusqu'à cinq boutons : Tous les records, Teamfight,
Ganks, Détail du score et Différentiel d'or. Si les records sont masqués, les
quatre autres restent disponibles.

**Détail du score** ouvre des pages privées : note et cinq dimensions
(Combat, Économie, Objectifs, Tempo, Impact), point fort / axe de progression,
comparaison des dimensions avec le MVP (ou le meilleur autre coéquipier), puis
classement des dix joueurs en deux pages. Les dimensions absentes restent « — ».
La note globale et les dimensions sont celles sauvegardées lors du récap.

**Différentiel d'or** ouvre un embed privé avec un PNG :
- une courbe alliés moins adversaires, comme `/lol_analyse_durant_la_game gold_team` ;
- segments bleus en avantage allié, rouges en retard, coupure exacte au passage par zéro ;
- fond clair et valeur affichée à chaque minute ;
- somme du totalGold des cinq joueurs de chaque équipe Riot ;
- un point par minute entière, avec une tolérance de retard de frame de 1 seconde ;
- aucune extrapolation, interpolation ou remplacement d'une minute par une frame finale partielle ;
- une interruption de la courbe lorsqu'une minute manque ;
- dernière minute mesurée et avantage maximal allié/adverse, du point de vue du compte du récap.

Le graphique est généré en mémoire, sans fichier partagé entre utilisateurs.
Le bouton Fermer retire aussi la pièce jointe. Les lectures SQL et le rendu
précèdent la réponse privée mais suivent l'acquittement du clic.

### Persistance

`match_recap_details` stocke un JSONB par (match_id, joueur). Le snapshot est
pris pendant la sauvegarde du match, avant l'envoi du récap, à partir des
scores déjà calculés et de la timeline déjà chargée. Il n'ajoute aucun appel
Riot. Les PUUID servent à identifier le joueur et à retrouver les vraies équipes
malgré le réordonnancement des listes du scoring ; seuls les résultats utiles
sont enregistrés, pas les PUUID.

La table est créée à la première sauvegarde. Si le rôle PostgreSQL n'a pas le
droit CREATE, appliquer `scripts/create_match_recap_details.sql`. Une erreur
de cette sauvegarde optionnelle est journalisée sans bloquer le récap.

Pour les anciens matchs, les vues essaient les tables existantes
`match_scoring` et `matchs_timestamp_gold`. Le score historique est identifié
par Riot ID + tag, jamais par l'index Riot brut ; l'or historique est filtré
sur le compte et remis dans le sens bleu/rouge. En l'absence de données
exploitables, le bouton l'indique explicitement. Les anciens messages doivent
être rechargés ou republiés pour afficher les nouveaux boutons.

### Recette

- Vérifier les cinq boutons, les deux derniers même si tous les records sont masqués.
- Naviguer dans le score jusqu'aux dix joueurs et contrôler le compte côté rouge.
- Ouvrir simultanément deux courbes de matchs différents ; fermer chaque vue.
- Vérifier les avantages positifs/négatifs, l'égalité, une seule minute et les trous.
- Redémarrer le bot et rouvrir les deux vues sans rappeler Riot.
