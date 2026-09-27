# MatchLoL — aperçu compact et records détaillés

## Affichage public

Après une analyse éligible (RANKED/FLEX/SWIFTPLAY d'au moins 15 min,
ou ARAM d'au moins 10 min), le récap sélectionne au maximum **trois
statistiques marquantes**, puis affiche leurs distinctions dans les sections
**Records All-Time**, **Records Saison** et **Records Perso**, comme l'ancien
affichage. Une statistique peut apparaître dans plusieurs sections : chaque
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
