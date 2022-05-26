# MarinSlash
Bot discord affichant des statistiques (API League of Legends, Twitch, Swarfarm)

Note à moi-même : il faudrait un notebook non-clean (pour la démarche), et un notebook clean

# Fonctionnalités

Les fonctions Discord sont repertoriés dans le dossier cogs.


## Projet 1 : LeagueofLegends

Utilisation de l'API de Riot Games, après avoir obtenu leur autorisation sur dossier.

## Automatisation

### Rapport de partie / Tracker

- Un joueur peut ajouter son compte au tracker
- Construis un rapport de chaque partie avec ses stats principales
- Affiche les bons points du joueur
- Affiche une notation / 10 de sa partie. Le joueur peut voir comment le score est calculé en affichant les corrélations entre les variables et le score final.
- Le score final est prédit sur la base du calcul d'op.gg, à partir d'une régression linéaire

### Records

- Les records des joueurs trackés sont enregistrés. Il peut donc retrouver son record et sur quel champion il l'a obtenu.

### Achievements

- Lorsqu'un joueur fait une bonne performance, il peut gagner une couronne. (Par exemple, s'il ne meurt pas de la partie)
- Chaque joueur peut comparer son nombre de couronnes aux autres joueurs du tracker.




