# MarinSlash
__Bot discord affichant des statistiques (API League of Legends, Twitch, Swarfarm)__

# Ressources

Pour diversifier mes compétences, le bot stocke des données dans :
- Des fichiers pickle (paramètres du bot)
- Un fichier texte (les identifiants de certains channels ou comptes Discord)
- Une BDD SQL avec sqlite3 et sqlalchemy (les data league of legends)
- Json pour les paris, car il y a des dictionnaires imbriquées qui doivent être facilement modifiables

Les visuels sont réalisés avec :
- Matplotlib
- Seaborn
- Plotly express
- Pygal

Autres librairies utilisées :
- Pandas
- Numpy
- Scikit-learn et skicit-image pour la régression linéaire et l'utilisation de carte League of Legends
- Discord, Discord.ext, Discord_slash et Asyncio pour le fonctionnement du bot
- RiotWatcher pour les requêtes à l'API de Riot Games
- Requests pour l'api de twitch
- Datetime

# Fonctionnalités

Les fonctions Discord sont repertoriées dans le dossier cogs.


## Projet 1 : LeagueofLegends

__Utilisation de l'API de Riot Games, après avoir obtenu leur autorisation sur dossier.__

## Automatisation

### Rapport de partie / Tracker


- Construis un rapport de chaque partie avec ses stats principales
- Un joueur peut ajouter/retirer son compte au tracker
- Affiche les bons points du joueur
- Affiche une notation / 10 de sa partie. Le joueur peut voir comment le score est calculé en affichant les corrélations entre les variables et le score final.
- Le score final est prédit sur la base du calcul d'op.gg, à partir d'une régression linéaire

 <p align="center">
  <img width="430" height="600" src="https://github.com/Tomlora/MarinSlash/blob/main/synthese_game.jpg?raw=true">
</p>

### Records

- Les records des joueurs trackés sont enregistrés. Il peut donc retrouver ses différents records et sur quel champion il l'a obtenu par rapport aux autres joueurs du tracker

### Achievements

- Lorsqu'un joueur fait une bonne performance, il peut gagner une couronne. (Par exemple, s'il ne meurt pas de la partie ou s'il participe à plus de 70% des kills de son équipe)
- Chaque joueur peut comparer son nombre de couronnes aux autres joueurs du tracker.

### Stats cumulés

- Un joueur peut voir ses stats cumulées depuis qu'il est inscrit au tracker.


### Challenges

Riot a mis en place récemment un site de défis, avec 232 disponibles. Par exemple, obtenir tous les champions du jeu ou réaliser des objectifs durant une ou plusieurs parties.

- Le bot peut afficher une synthèse des points de défis obtenus, et faire des comparaisons pour chaque défi entre les joueurs du tracker.


## Analyse

- Le joueur peut analyser certaines statistiques individuelles ou collectives d'une partie, par rapport aux autres joueurs :

Ai-je fait beaucoup de dégats sur les ennemis ?

Ai-je amassé beaucoup de gold, me permettant d'être plus forts, par rapport aux autres ?

Où étais-je à 15 minutes de jeu sur la carte ? *(Pour cela, skicit-image est nécessaire afin d'avoir une image fiable sur laquelle poser les points de position)*

Comment notre équipe a évolué au cours de la partie ?

A quel moment ai-je utilisé mon item ?

__Le bot peut répondre à toutes ces questions.__


## Teamfight Tactics

- Ajout progressif des mêmes fonctionnalité sur TFT.


## Competitif pro

### Statistiques

- Le bot peut afficher les statistiques principales des joueurs pros dans toutes les compétitions gérées par Riot Games. (Corée, Chine, USA, Europe, Amérique du Nord...)
- Lister les joueurs pros de chaque équipe
- Affiche les durées de contrat de chaque joueur

### Alarme

- Le bot peut servir d'alarme pour les joueurs qui souhaitent suivre certaines compétitions. En effet, via un calendrier, le bot peut annoncer lorsqu'une game pro commence.

### Fantasy

Le bot permet de jouer à un jeu qui se nomme la Fantasy League.
- Le concept est que chaque joueur dispose de 50 points, et peut miser ses points sur des matchs de certaines compétitions majeures.

S'il gagne, le joueur remporte la mise en fonction d'une côte calculée par un site de pari sportif.

S'il perd, il perd la totalité de sa mise. 


## Projet 2 : Musique

Le bot peut être un DJ dans un salon vocal Discord.


## Projet 3 : Summoners Wars

En utilisant un fichier json généré par Summoners Wars, le bot peut afficher divers informations sur son compte ou sur les contenus de guilde.


## Projet 4 : Twitch

Détermine dans un tracker si une personne a lancé son stream twitch, et sur quel jeu.





