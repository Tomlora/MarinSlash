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

Un ancien récap sans ces données affiche une explication de cette limite.
Ses notes restent consultables, mais les détails ne sont pas reconstruits
avec les ratios actuels. Un récap recalculé et sauvegardé par la nouvelle
version contiendra les nouvelles pages.

Les tests confrontent les sommes de points au calcul réel pour les 21 profils,
avec données complètes, absentes et valeurs nulles, puis contrôlent la sélection
du joueur bleu/rouge, la conservation JSON et les limites des pages Discord.
Une divergence future entre formule et explication empêche la sauvegarde
d'une explication trompeuse ; les tests doivent échouer jusqu'à leur alignement.
