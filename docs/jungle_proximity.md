# Jungle proximity dans Ganks

Le bouton Ganks conserve son résumé et sa chronologie. Deux pages intermédiaires
présentent les quatre laners alliés, puis les quatre adversaires (TOP, MID, ADC,
SUPP), avec l'emote du champion et le nom. Chaque ligne compare son jungler au
jungler adverse, du point de vue du joueur affiché. Les junglers ne sont pas
comparés à eux-mêmes.

## Définition v1

- Fenêtre : de 2:00 inclus à 14:00 exclu, pour éviter le regroupement initial et
  rester dans la phase de lane utilisée par le composant Ganks.
- Distance euclidienne <= 2 000 unités entre les deux positions d'un même relevé.
- Pourcentage = 100 × relevés proches / relevés utilisables pour cette paire.
- Les deux joueurs doivent avoir une position valide et une santé connue > 0.
  Les positions dans un rayon de 2 500 unités des coins (0, 0) et (15000, 15000)
  sont exclues pour écarter les bases. C'est une approximation géométrique.
- Aucun trajet interpolé, aucun temps de présence reconstruit. Les relevés Riot
  sont généralement espacés d'une minute : un passage bref peut être manqué.
  Les comptes proches/utilisables et utilisables/relevés de la fenêtre sont affichés.
- Une position ou une santé absente est exclue du dénominateur. Aucun relevé
  utilisable donne `—`, et non `0 %`. Un timestamp dupliqué compte une seule fois.
- Jungler identifié par teamPosition/individualPosition, puis Smite seulement
  si aucun rôle jungle n'est indiqué. Plusieurs candidats donnent une donnée
  indisponible. L'équipe suivie est identifiée par PUUID et teamId natifs.

Ces seuils définissent un indicateur descriptif propre au bot, pas un score de
qualité ni un gank confirmé. Les pourcentages par joueur ne s'additionnent pas :
un jungler peut être proche simultanément de l'ADC et du support. Les échantillons
retenus pour les deux junglers peuvent différer (mort, base, données absentes).

## Sauvegarde et compatibilité

Snapshot versionné `data.jungle_proximity` dans le JSONB `match_recap_details`,
avec scores, or, carte et profils. Pas de migration ni d'appel Riot supplémentaire.
Le clic recharge le snapshot du couple `(match_id, joueur)` dans le worker de
lecture existant, après acquittement privé. La proximité reste lisible même si les
tables de ganks sont absentes. Les anciens récaps indiquent qu'une réanalyse est
nécessaire ; une réanalyse utilise le pipeline existant, sans recalcul au clic.

Base : master après fusion des PR53 et PR54. Vérification réelle à effectuer sur
Discord après déploiement : bouton Ganks, page Alliés puis Adversaires, noms,
emotes, pourcentages, retour à la chronologie, ancien récap et compte côté rouge.
