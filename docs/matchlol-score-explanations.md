# Explication des cinq dimensions du score

La v4 ajoute les références de durée et les bonus réellement appliqués. Voir
[le barème v4](matchlol-scoring-v4.md). Les anciennes explications v3 sauvegardées
restent lisibles ; les descriptions ci-dessous couvrent le fonctionnement général.

Le bouton **Détail du score** présente, après la vue d'ensemble, des pages pour
Combat, Économie, Objectifs, Tempo et Impact. Elles concernent uniquement le
joueur du récap ; la comparaison et le classement existants restent à la suite.
Les flèches habituelles parcourent toutes les pages.

Chaque dimension indique ce qui limite le plus sa note, puis détaille :

- la valeur observée chez le joueur et ce qu'elle signifie ;
- les repères réellement appliqués par le bot, adaptés au rôle et au profil ;
- la note du critère, son poids et les points qu'il apporte sur 10 ;
- l'addition permettant de retrouver la note affichée, avec les arrondis.

Par exemple, un critère noté 2/10 qui compte pour 35 % apporte 0,70 point
sur les 3,50 possibles dans cette dimension. Les cinq dimensions décrivent
la contribution, qui représente 30 % du score global v3 ; elles ne sont pas
une décomposition des 70 % statistiques.

Les valeurs manquantes sont signalées avec le traitement réellement appliqué :
note neutre de 5/10 pour les événements indisponibles, exclusion d'un élément
de l'utilité du support si les autres sont disponibles. Une valeur connue
égale à zéro reste une vraie observation. Les supports tanks/utilitaires
voient les soins aux alliés, boucliers et contrôles utilisés par leur barème.

## Conservation et compatibilité

Les explications sont construites à partir des résultats intermédiaires du
calcul et de ses références, puis conservées dans le JSON existant
`match_recap_details.data`, sur la seule entrée du joueur suivi par PUUID.
Ouvrir le bouton ne recalcule rien : les futurs changements de ratios en BDD
ne modifient pas l'explication enregistrée. Aucun appel Riot supplémentaire
ni migration SQL n'est nécessaire. Ouvrir le bouton ne change pas la note sauvegardée.

Un récap sans ces données conserve ses notes, mais les détails ne sont pas
reconstruits avec les ratios actuels. Leur absence ne prouve pas que le récap
est ancien : le calcul peut ne pas fournir le contexte, ou la sauvegarde SQL
peut échouer. Recalculer sans corriger la cause ne garantit pas les pages.

Les tests confrontent les sommes de points au calcul réel pour les 21 profils,
avec données complètes, absentes et valeurs nulles, puis contrôlent la sélection
du joueur bleu/rouge, la conservation JSON et les limites des pages Discord.
Une divergence future entre formule et explication empêche la sauvegarde
d'une explication trompeuse ; les tests doivent échouer jusqu'à leur alignement.

## Diagnostic des explications absentes

La sauvegarde enregistre `explanation_status` uniquement sur le joueur suivi :

- `available` : les explications ont été produites et sérialisées ;
- `missing_metrics` : pas de métriques détaillées pour ce joueur ;
- `missing_context` : métriques présentes, sans contexte d'explication (vérifier
  notamment les versions des modules chargés si le bot a été rechargé à chaud) ;
- `inconsistent_context` : détail écarté car sa note diffère du résultat réel ;
- `invalid_context` : erreur dans le détail, conservée dans les logs avec traceback.

Une erreur du détail n'empêche plus de sauvegarder les autres notes et l'or.
Ces cas journalisent l'identifiant du match, du compte, la version de scoring
et la raison. Un échec global de sauvegarde reste journalisé sous
`Sauvegarde des détails du récap impossible` avec match, compte et traceback.
Si seule la table `match_scoring` fournit les notes, le bouton indique l'absence
du snapshot ; il ne prétend plus que le match est simplement trop ancien.
Les snapshots précédents sans statut restent de cause inconnue.

Les tests PostgreSQL exécutent le vrai calcul, la méthode `save_data`, l'écriture
JSONB, la relecture SQL et la pagination du bouton pour les deux équipes, à
20 et 40 minutes, sur un match nouveau ou déjà enregistré. Les cinq explications
doivent survivre à la disparition des métriques en mémoire.
