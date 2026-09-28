# Scoring MatchLoL v4 : rôle, kit et durée

La v4 conserve 70 % statistiques + 30 % contribution. Elle corrige les seuils
communs sévères et donne le même sens au repère central : 5/10. Ces références
et courbes sont **provisoires**, déterminées par conception et non ajustées sur
une distribution historique de matchs. Les tests valident les propriétés du
calcul, pas une équité statistique démontrée en production.

## Durée

Le calcul utilise `gameDuration` en secondes, converti en vraies minutes. Les
attentes par minute dépendent aussi du moment où la partie se termine. Les
facteurs suivants multiplient la référence de rôle/profil à 30 minutes :

| Mesure | 10 min | 20 min | 30 min | 40 min | 60 min |
| --- | ---: | ---: | ---: | ---: | ---: |
| Dégâts aux champions/min | 0,50 | 0,70 | 1,00 | 1,25 | 1,40 |
| Or/min | 0,75 | 0,90 | 1,00 | 1,08 | 1,12 |
| CS/min | 0,85 | 0,95 | 1,00 | 0,95 | 0,85 |
| Vision/min | 0,55 | 0,75 | 1,00 | 1,15 | 1,25 |
| Soins + boucliers alliés/min | 0,50 | 0,70 | 1,00 | 1,20 | 1,35 |
| Contrôles/min | 0,70 | 0,85 | 1,00 | 1,10 | 1,15 |
| Morts/min | 0,70 | 0,85 | 1,00 | 1,10 | 1,15 |

Entre ces points, interpolation linéaire ; en dehors, maintien du facteur de
la borne. Aucun saut de note en franchissant 20, 30 ou 40 minutes. Les formes
expriment des hypothèses de montée en puissance et de phase de jeu ; elles
doivent être confrontées à l'historique avant de prétendre refléter la population.

Exemple avec les ratios fournis : tank jungle, dégâts attendus/min = 350 à
30 min, or attendu/min = 380. Les références deviennent 245/342 à 20 min et
437,5/410,4 à 40 min. Son dégâts/or attendu est donc environ 0,716 à 20 min,
0,921 à 30 min, 1,066 à 40 min. Dans chaque cas, respecter le repère vaut 5/10.

Les parts de participation utilisent des occasions observées, pas un compteur
absolu multiplié par la durée. L'avance en or/CS à 15 min reste une photo à
15 min et ne change pas parce que la partie finit à 20 ou 40 min. Sans observation
valide à 15 min, le critère est exclu ; si aucun critère du Tempo n'est connu,
son socle est neutre à 5/10. Les bonus observés peuvent ensuite s'ajouter.

## Courbes et composition

Pour les mesures positives de contribution, avec `r = observé / attendu` :
`note = 10*r²/(1+r²)`. Une valeur attendue vaut 5, sa moitié vaut 2, son double
vaut 8. Un zéro connu vaut zéro, mais une observation positive ne devient plus
zéro à cause d'un seuil minimum universel. La survie utilise la courbe inversée
sur les morts individuelles attendues à cette durée. Les morts des alliés ne
modifient plus la note de survie.

- **Combat** : KDA 35 %, participation aux éliminations 35 %, survie 30 %.
  KDA par rôle avec facteur 0,85 pour tank/fighter. La participation utilise le
  rôle/profil et est rapprochée de 5 quand l'équipe a peu d'éliminations.
- **Économie** : dégâts/or adapté 50 %, CS/min 25 %, or/min 25 %. Support non
  utilitaire : dégâts/or et or/min à parts égales. Support tank/utilitaire :
  or/min seul. Jungle utilitaire : CS/min et or/min à parts égales. Le critère
  parts de dégâts/parts d'or redondant est retiré.
- **Objectifs** : participation aux monstres épiques et tours alliées, vision
  et faible poids des balises achetées. Dernier coup et assistance sont égaux.
  Aucun sous-score Baron/dragon à zéro à cause d'un objectif d'un autre type.
  Sans prise alliée de la catégorie, le critère est exclu. Le volume brut de
  dégâts et les derniers coups sur tours ne sont plus des critères supplémentaires.
- **Tempo** : avance en or à 15 min 70 %, CS 30 %. Support : or uniquement.
  Égalité = 5 ; progression douce `5 + 4*tanh(écart / dispersion)`, dispersion
  1 500 or (750 support) ou 30 CS. Premier sang/première tour : bonus de 0,25
  chacun, assistance comprise. Solo kill avant 15 min top/mid : +0,10, maximum
  +0,30. Sans ces actions, aucun malus. Dimension plafonnée à 10.
- **Impact — apport à l'équipe** : dégâts/min adaptés 60 %, participation 40 %.
  Utilitaire : utilité 80 %, participation 20 %. Support hybride connu : utilité
  50 %, dégâts 30 %, participation 20 %. Le libellé ne prétend pas mesurer une
  causalité sur la victoire. Le partage d'or n'est plus réutilisé ici ni en Tempo.

Les poids de dimensions par rôle et leurs ajustements BDD restent normalisés.
Les critères absents/non applicables sont exclus avec redistribution au sein
de la dimension. Une dimension entièrement non observée garde un socle neutre.
La participation aux objectifs est rapprochée de 5 avec le facteur `n/(n+2)` :
une prise sur une ne suffit pas à obtenir 10. Les attentes de présence sont
des proportions par rôle (top et jungler n'ont pas les mêmes attentes).

La composante statistique garde KDA, CS/min, dégâts/min, or/min, vision/min et
participation, avec leurs références de durée. Parts de dégâts et dégâts reçus
sont retirés de sa pondération ; les poids restants du rôle sont renormalisés.
Les utilitaires principaux n'y sont plus notés sur les dégâts. L'utilité est
évaluée dans Impact seulement, et non quatre dimensions plus les statistiques.
La transformation statistique est centrée à 5, bornée au minimum à 1 et au
maximum théorique à 10. Le plancher global de contribution reste 1.

Il reste volontairement des recouvrements entre statistiques et contribution
(KDA, CS, production, vision, participation) : la v4 réduit les doublons les plus
problématiques, sans prétendre que les cinq dimensions sont indépendantes.

## Kits, profils et limites des observations

L'applicabilité des soins/boucliers dépend du kit/profil avant de regarder la
valeur observée. Un tank support inconnu sans capacité d'aide alliée déclarée
est évalué sur ses contrôles seuls. Pour les kits concernés, soins/boucliers
pèsent 70 %, contrôles 30 %, avec redistribution si une composante manque.
Un zéro connu sur une capacité attendue reste observé. La liste de kits de
`scoring_v4.py` est une classification maintenue manuellement, pas une déduction
automatique du build ou des capacités via réseau. Les références 100/400 par
minute et 0,6/1,5 secondes/minute restent des heuristiques à calibrer.

Ivern jungle devient utilitaire et bénéficie d'un repli de ratios dédié. Les
supports hybrides connus, dont Senna, peuvent être crédités de leur aide alliée.
ADC/ASSASSIN est sélectionnable pour les ADC agressifs et les tags correspondants.
ADC/FIGHTER a un repli dédié. Les 21 lignes exportées ne sont pas réécrites en BDD.
Les coefficients `damage_share_mult` et `damage_taken_share_mult` sont conservés
pour compatibilité et diagnostic ; ils ne pilotent plus les critères supprimés.

Les événements ne décrivent que les participants enregistrés par Riot : le
contrôle de zone non crédité, les sacrifices utiles et certaines actions hors
écran restent des limites. L'absence de prise alliée ne prouve pas l'absence
d'une occasion manquée. Le scoring ne tente pas d'inventer cette information.
Une timeline partielle peut omettre des prises : elle n'est pas reconstruite.

Un rôle inconnu et les modes autres que RANKED, FLEX, NORMAL, SWIFTPLAY et CLASH
reçoivent des valeurs neutres de compatibilité, signalées comme
non évaluées dans le détail. Le classement ARAM distinct reste hors de cette
calibration. La v4 reste conçue pour les modes classiques.

## Sauvegarde et explications

Les composantes effectivement additionnées, références de durée, exclusions
et bonus sont sauvegardés dans le JSON du joueur suivi du récap (version 2 de
l'explication, scoring 4.0). Le bouton ne recalcule pas avec les nouveaux ratios.
Les explications de version 1 restent lisibles. Les anciens récaps sans détail
conservent leur message de disponibilité. Aucun recalcul massif d'historique,
nouvelle requête Riot ni migration SQL.

Les colonnes historiques de sous-scores retirés restent présentes pour
compatibilité ; elles sont neutres et ne doivent pas être utilisées pour
reconstruire la v4. Le JSON versionné est la source de l'explication. Les
colonnes brutes (parts, dégâts, compteurs) gardent leur valeur observée.

## Validation

Tests des 21 profils à 20/30/40 min, égalité à la référence, continuité des
courbes, absence de bonus mécanique à durée longue, conservation de la mesure
à 15 min, kits sans soins, hybrides, données absentes versus zéro, objectifs
alliés/adverses, neutralité hors modes/rôles couverts, invariance bleu/rouge,
écritures SQL, sommes expliquées et taille des pages Discord.

Avant toute calibration empirique, exporter les matchs déjà stockés par rôle,
champion, mode, patch, niveau et durée. Comparer distributions, taux de notes
extrêmes et changements de classement, avec repli vers rôle/profil pour les
petits échantillons. L'export des seuls coefficients ne permet pas cette étape.
