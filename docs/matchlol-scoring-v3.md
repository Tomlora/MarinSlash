# Scoring MatchLoL v3.0

La note de performance devient **70 % statistiques + 30 % contribution**.
La contribution est la moyenne des cinq dimensions existantes (combat,
économie, objectifs, tempo, impact), avec les poids du rôle et les ajustements
du profil. Le détail du score affiche les deux composantes : les cinq dimensions
ne sont pas, à elles seules, la décomposition de la note finale.

Cette pondération et les références d'utilité ci-dessous sont des choix
heuristiques initiaux, pas les résultats d'un entraînement sur l'historique.

## Statistiques et profils

- Les z-scores sont limités à [-3, +3] avant pondération et sigmoïde. Le KDA
  utilise `(kills + assists) / max(deaths, 1)`, sans bonus supplémentaire à zéro
  mort. Une seule statistique extrême ne peut plus imposer une note proche de 10.
- Moyenne **et écart-type** sont ajustés par le multiplicateur du profil.
- L'absorption de dégâts est positive pour les profils TANK/FIGHTER et inversée
  pour les autres. Le multiplicateur numérique ne sert plus de classification.
- `scoring_profile_defaults.json` reprend les 21 profils et leurs 12 paramètres
  numériques fournis dans `scoring_profile_ratios.csv` le 28 septembre 2026.
  La BDD reste prioritaire. Les lignes/champs absents, multiplicateurs non
  positifs et nombres non finis utilisent les valeurs de secours du profil.
  Il n'y a aucune écriture dans `scoring_profile_ratios`.
- Les alias UTILITY/MIDDLE/BOTTOM sont normalisés avant sélection du profil.

## Contribution et utilité

Les objectifs et le tempo influencent désormais la note finale. L'avance en or
de l'équipe reste un diagnostic enregistré, mais n'attribue plus directement
un bonus individuel. Les parts attendues d'or et de dégâts sont calculées à
partir des cinq rôles/profils de l'équipe, au lieu d'attendre 20 % pour chacun.

Les supports TANK et SUPPORT_UTILITY utilisent les champs Riot déjà présents
dans le match : `totalHealsOnTeammates`, `totalDamageShieldedOnTeammates` et
`timeCCingOthers`. Aucun appel API supplémentaire n'est ajouté.

Références provisoires pour une utilité de 5/10 :

| Profil | Soins + boucliers aux alliés/min | Secondes de contrôle/min |
| --- | ---: | ---: |
| SUPPORT_UTILITY | 400 | 0,6 |
| TANK support | 100 | 1,5 |

Chaque composante est linéaire de 0 à deux fois cette référence et bornée
entre 0 et 10. L'utilité est la moyenne des composantes disponibles. Il faut
les deux champs soins/boucliers pour calculer leur composante, et un vrai zéro
est conservé. Les soins personnels ne sont jamais ajoutés.

Si l'utilité est disponible, elle représente 20 % de la composante statistique
de ces supports. Elle remplace aussi les attentes de dégâts dans certaines
dimensions de contribution. Si les champs manquent, l'utilité reste neutre
(5/10) dans ces dimensions et la composante statistique garde ses poids usuels.

Les dégâts aux tours/objectifs et achats de pinks sont ramenés à une durée de
référence de 30 minutes. Cela limite le bonus lié à la seule durée de partie.
Les dégâts aux objectifs peuvent aussi inclure les tours : ces signaux restent
partiellement corrélés, tout comme dégâts/min et part des dégâts.

## Identité et timeline

- Les événements Riot sont reliés à `participantId`, puis à l'ordre d'affichage.
  Un récap côté rouge ne transfère plus ses objectifs/first blood/gold @15 à
  l'adversaire. Les vrais `teamPosition` remplacent les rôles supposés par index.
- Les décès d'équipe sont la somme des décès, exécutions comprises.
- Les grubs augmentent le numérateur **et** le dénominateur des objectifs.
  Les assistants uniques reçoivent le même crédit que le dernier coup ; les
  anciens bonus au dernier coup sont supprimés. Le dénominateur est le total
  pondéré des objectifs des deux équipes, pas uniquement ceux gagnés par le joueur.
- Tous les chemins de scoring extraient les données early game, y compris les
  commandes qui n'appellent pas `MatchLol.run()`.
- Une frame @15 n'est retenue qu'entre 900 et 905 secondes. Une fin de partie
  avant 15 minutes ou un participant absent ne devient pas une statistique @15.
  Gold et CS ont des indicateurs de disponibilité indépendants.
- Sans timeline, les composantes temporelles sont neutres (5/10). Sans objectif
  observé, la participation ne reçoit pas artificiellement zéro. Les statistiques
  de fin de partie connues restent utilisées. Une timeline partiellement tronquée
  n'est pas reconstruite : sa couverture reste une limite à surveiller.
- Les solo kills de toute la partie restent enregistrés ; seul leur sous-ensemble
  avant 15 minutes intervient dans le tempo.

## Classement, stockage et modes

Le classement utilise les notes non arrondies (précision de comparaison de
12 décimales). Les véritables égalités partagent un rang : 1, 1, 3. Les résumés
marquent tous les co-MVP/co-ACE ; les interfaces n'affichant qu'un champion
utilisent un représentant stable choisi par participantId.

Les récaps classique et moderne sauvegardent le même rang pour les modes
classiques ; `matchs.mvp` reçoit un rang, jamais une note sur 10. Les tables
communes au match utilisent désormais `participantId - 1` comme `player_index`.
Un recalcul met aussi à jour l'identité de la ligne pour remplacer correctement
une ancienne ligne enregistrée dans l'ordre d'affichage. Les consommateurs
d'historique identifient déjà les joueurs par Riot ID + tag.

La version, les composantes de la note et les nouveaux champs d'utilité sont
sauvegardés dans le JSON existant de `match_recap_details` (par match et compte).
Les anciennes colonnes `zscore_score` et `breakdown_score` gardent leur sens de
composantes. Aucun nouveau schéma SQL ni recalcul global d'historique n'est requis.
Les anciennes parties gardent leurs données jusqu'à un éventuel recalcul explicite.
Les moyennes historiques de rang peuvent donc traverser plusieurs versions ; ne
pas les présenter comme une comparaison homogène de méthodes.

Le classement MVP spécifique ARAM continue d'utiliser le RandomForest existant
dans le récap. La correction des unités par minute lui fournit désormais des
valeurs en vraies minutes (l'ancien calcul divisait déjà des minutes par 60).
Son classement peut donc changer : son modèle n'est pas réentraîné ici. Les
références par rôle de la v3 ne sont pas validées pour ARAM/Arena/Swarm, et une
note détaillée obtenue pour ces modes ne doit pas servir d'évaluation calibrée.

## Validation et déploiement

Tests hors ligne : invariance bleu/rouge, ordre des participants, rôles, durée,
timeline absente/partielle, matchs courts, grubs, assistants, objectifs,
KDA extrême, soins/boucliers, exécutions, égalités, profils BDD incomplets,
identités SQL et sauvegarde JSON. La CI exécute `tests/test_match_scoring.py`.

Après fusion et redémarrage/rechargement du bot, vérifier quelques nouveaux
récaps et leurs détails. Aucune modification des ratios BDD n'est nécessaire.
Avant de modifier à nouveau les poids, mesurer les distributions de score et
fréquences MVP par rôle/profil, niveau, durée et victoire ; examiner séparément
les parties sans timeline et les matchs ARAM. Les tests garantissent les
invariants calculatoires, pas une équité statistique démontrée en production.
