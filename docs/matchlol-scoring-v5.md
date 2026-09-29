# Scoring MatchLoL v5 : échelles atteignables et cohérentes

Le barème v4 notait une participation parfaite à 100 % au maximum 6,5/10
avec une référence de 66 % et 32 éliminations d'équipe. Il demandait aussi
15,1 CS/min pour 8/10 avec une référence de 7,55. La v5 corrige les courbes
pour chaque famille de métriques. Elle conserve les références de rôle,
les ratios de profil en BDD, les courbes de durée, les règles d'applicabilité
des kits et la formule globale 70 % statistiques + 30 % contribution.

Les repères ci-dessous sont des choix de conception provisoires, **pas des
percentiles ni des moyennes mesurées**. Il faudra un historique de parties
par rôle, champion, durée, niveau, patch et mode pour les calibrer.

## Production : une échelle par métrique

Interpolation linéaire continue entre les repères. Zéro observé vaut zéro ;
la moitié de la référence vaut 2/10 ; la référence vaut 5/10. Une production
positive sous la référence ne reçoit plus automatiquement zéro. Le maximum
est 10, atteint au dernier repère, puis plafonné.

| Critère | Ratio pour 8/10 | Ratio pour 10/10 |
|---|---:|---:|
| Éliminations et assistances par mort | 2 | 3 |
| Sbires et monstres/min | 1,25 | 1,50 |
| Or/min | 1,35 | 1,65 |
| Dégâts aux champions/min | 1,60 | 2,20 |
| Dégâts/or | 1,50 | 2 |
| Vision/min | 1,60 | 2,40 |
| Soins/boucliers et contrôles/min | 1,70 | 2,50 |
| Balises de contrôle achetées | 1,50 | 2,50 |

La référence dépend du rôle et du profil. Dégâts, or, CS, vision, utilité
et contrôles conservent les courbes de durée v4 (interpolation aux points
10/20/30/40/60 minutes, valeurs extrêmes figées). Dégâts/or utilise le
rapport des références dégâts/min et or/min. Le KDA n'est pas artificiellement
multiplié par la durée. Le KDA sans mort divise toujours par 1 ; son poids
et son plafond empêchent une valeur extrême de dominer la moyenne.

## Participation, survie et avance à 15 minutes

- Participation aux éliminations et aux objectifs : 0 % vaut 0, la référence
  du rôle vaut 5, le milieu entre cette référence et 100 % vaut 8, 100 % vaut 10.
  Aucune cible ne dépasse 100 %. L'évaluation est rapprochée de 5 seulement
  sous 8 éliminations d'équipe ou 3 prises alliées : facteur `min(1, n/seuil)`.
  Zéro occasion exclut le critère, avec redistribution de son poids.
- Objectifs : les références restent TOP 35/45 %, JUNGLE 75/35 %, MID 50/45 %,
  ADC 55/50 %, SUPPORT 70/50 % (épiques/tours). Seuls dernier coup et assistance
  enregistrés sont évalués à valeur égale. Zoning et pression indirecte restent
  hors mesure ; le texte le précise. Pas de malus spécifique pour un Baron absent.
- Survie : zéro mort vaut 10, la moitié des morts de référence vaut 8,
  la référence vaut 5, 1,5 fois la référence vaut 2. Au-delà, décroissance
  `2 / (1 + ratio - 1,5)` vers zéro, sans seuil brutal. Les morts de référence
  dépendent du rôle, du profil et de la durée, jamais des morts alliées.
- Avance à 15 minutes : égalité 5 ; +1 500 or (+750 support) ou +30 CS vaut 8 ;
  le double vaut 10. Retards équivalents : 2 et 0. Interpolation entre ces
  points, bornes 0/10 au-delà. La durée finale ne change pas une mesure à 15 min.
  Le support ne reçoit toujours aucun critère CS dans le Tempo.
- Bonus Tempo : premier sang/première tour +0,25 chacun, assistance comprise ;
  solo avant 15 min +0,10 uniquement top/mid, maximum +0,30. Bonus total plafonné
  par la place restante jusqu'à 10. Le rôle exclu est expliqué explicitement.
- Utilité : seules les capacités pertinentes pour le kit sont attendues.
  Une donnée manquante est exclue, un zéro connu reste zéro. Ivern conserve
  son traitement utilitaire ; les supports hybrides gardent dégâts et utilité.

## Agrégation

Les 70 % statistiques sont désormais une moyenne pondérée des **mêmes notes
de critères** que dans les dimensions. Il n'y a plus de seconde transformation
logistique. Les poids de rôle existants sont renormalisés après exclusion des
parts de dégâts/dégâts reçus, du DPS pour les kits utilitaires principaux et
des données absentes. L'utilité disponible ajoute un poids brut de 0,20 pour
un kit principalement utilitaire et 0,10 pour un support hybride, avant
renormalisation. Le support conserve un poids CS nul.

Les cinq dimensions et leurs poids v4 restent conservés, ajustements BDD
compris, puis renormalisés. Le minimum caché de 1/10 de la contribution est
supprimé : le résultat correspond exactement à la somme pondérée affichée.
Les recouvrements entre les deux blocs restent intentionnels : la formule
globale n'est pas une mesure de cinq facteurs statistiquement indépendants.

Les colonnes SQL `z_*` restent des diagnostics historiques ; `weighted_z`
vaut zéro en v5 et n'intervient plus dans la note. `zscore_score` conserve
son nom pour compatibilité mais contient la nouvelle moyenne statistique.
Les modes/rôles non couverts restent explicitement neutres à 5/10.

## Explications et historique

Les textes utilisent les repères des fonctions de calcul, les valeurs avec
unités et des décimales françaises. Un critère au-dessus de 5 n'est plus
présenté comme une faiblesse parce qu'il n'a pas 10. Les cinq dimensions
disposent chacune d'une page complète, total compris, avec jusqu'à six champs.
Les critères absents ne sont pas présentés comme de vrais 5/10 à poids zéro.

Les snapshots incluent la version 5.0, les références, les composantes
statistiques et les poids des dimensions. Les snapshots v3/v4 restent lus
avec leurs valeurs sauvegardées, sans recalcul au clic. Pas de migration,
d'écriture des ratios BDD, de nouvel appel Riot ou de recalcul de l'historique.
Le worker asynchrone de PR49 reste inchangé.

## Vérification du cas EUW1_7998216201

Reproduction hors ligne à partir des valeurs et références fournies, durée
1880 secondes ; les ajustements de profil implicites dans le récap sont figés.
Ce n'est pas une récupération de la partie auprès de Riot ni de la BDD live.

| Dimension | v4 reproduite | v5 |
|---|---:|---:|
| Combat | 7,34 | 8,12 |
| Économie | 6,69 | 8,17 |
| Objectifs | 5,82 | 6,40 |
| Tempo | 8,00 | 8,00 |
| Impact | 7,20 | 8,79 |

La participation passe de 5,64 à 7,14 et le farm de 6,10 à 8,01. La composante
statistique passe de 9,34 à 8,88 : les critères partagent la même échelle,
la correction n'est donc pas une hausse uniforme de toutes les notes.

Les tests couvrent les 21 profils à 10/20/30/40/60 minutes, les bornes,
la continuité, la monotonie, les petits échantillons, les exclusions, les
sommes, le cas Tristana, l'historique, la pagination et la persistance JSONB.
