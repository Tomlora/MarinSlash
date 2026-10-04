# Caractéristiques des dix joueurs

Le bouton **Caractéristiques des joueurs** du récap ouvre une réponse privée avec
deux pages : cinq **alliés**, puis cinq **adversaires**. L'équipe du compte suivi
est identifiée par son PUUID et son véritable `teamId` Riot ; jouer côté rouge
ne renverse pas les libellés. Les joueurs sont ordonnés par rôle.

Chaque fiche contient le nom et tag, l'emote du champion (ou son nom si l'emote
manque), le winrate global Solo/Duo et ses victoires/défaites, le même bilan sur le
champion joué, le rôle principal et sa proportion, le rôle joué, le statut OTP et
l'autofill probable avec la fréquence du rôle joué. Les dix joueurs sont inclus,
y compris le compte suivi et les petits historiques. Aucun seuil de bon/mauvais
winrate ne masque les fiches.

Les labels OTP/autofill conservent les heuristiques des insights : au moins 20
parties sur le champion et part entière >70 % pour OTP ; fréquence du rôle joué
≤15 % et historique de plus de 30 parties pour l'autofill (estimation, pas une
confirmation du matchmaking). Les valeurs de fréquence restent visibles même
quand ces seuils ne sont pas atteints. Les insights publics ne sont pas modifiés.

## Acquisition et conservation

`external_data.py` capture les valeurs avant les filtres de présentation :

- Mobalytics : comptes `wins/losses` de `RANKED_SOLO`, statistiques champion avant
  le seuil de 30 parties et les valeurs de repli, historique de rôles déjà reçu.
- U.GG : comptes exacts du classement Solo/Duo, historique champion déjà chargé,
  rôles récents déjà reçus. Le rang est réinitialisé à chaque joueur pour éviter
  qu'une réponse absente réutilise celui du joueur précédent.

Les lignes d'un même champion sont additionnées (par rôle chez Mobalytics). Une
défaite peut être calculée par `totalMatches - wins` ; aucun compte n'est déduit
d'un pourcentage arrondi. Un historique valide sans le champion joué donne
0 V / 0 D, alors qu'un profil absent reste explicitement indisponible. Les noms
identiques avec des tags différents sont distingués par le PUUID.

Le snapshot versionné est enregistré dans `match_recap_details.data.players`,
avec les autres détails du récap. Il persiste après redémarrage et n'est pas
recalculé au clic. Les anciens récaps sans snapshot affichent une explication.
La table JSONB existante suffit, sans migration supplémentaire.

Aucune collecte n'est activée et aucun appel Riot, U.GG ou Mobalytics n'est ajouté.
Les données dépendent donc des fournisseurs et de la collecte existante. Les
périodes couvertes par le classement, les champions et les rôles peuvent différer
(notamment les rôles récents U.GG).

La vue utilise l'acquittement privé et le chargement en thread des vues de match
existantes. Les tests couvrent les vrais chemins d'acquisition avec APIs simulées,
les comptes exacts, les faibles échantillons, les joueurs manquants, la persistance
PostgreSQL, l'ordre des équipes et les composants interactions.py 5.13.2.
