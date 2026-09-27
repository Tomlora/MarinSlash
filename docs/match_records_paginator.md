# MatchLoL — aperçu compact et records détaillés

## Affichage public

Après une analyse éligible (RANKED/FLEX/SWIFTPLAY d'au moins 15 min,
ou ARAM d'au moins 10 min), le récap affiche au maximum **trois
statistiques marquantes** plutôt que les mêmes exploits répétés dans
All-Time / Saison / Personnel. Les scopes sont indiqués sur une seule ligne.
Les records historiques absolus passent en priorité. Une diversité de
statistiques est recherchée pour les autres places.

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
des IDs déterministes. Les données sont rechargées depuis PostgreSQL à
chaque interaction : le **bouton public reste utilisable après un
redémarrage** du bot. Les réponses éphémères restent soumises aux durées
d'accès imposées par Discord.

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
2. Choisir All-Time + personnel : une seule statistique dans le récap,
   deux distinctions réparties dans leurs pages respectives.
3. Choisir 10, 25 puis 50 records : changer de scope, atteindre
   la dernière page, vérifier les limites de cinq champs par embed.
4. Cliquer sur le bouton d'une véritable partie éligible : le
   récap public n'est pas édité ; la réponse est privée.
5. Redémarrer le bot puis cliquer sur un ancien bouton public
   depuis un message dont le snapshot existe toujours.
6. Désactiver tracker.save_records pour un compte et vérifier
   qu'aucun record ni bouton trompeur n'apparaît dans /game.
