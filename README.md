# MarinSlash
__Bot discord affichant des statistiques (League of Legends, TFT, Twitch, Swarfarm) sous forme visuel__

Le bot collecte, traite et réutilise les données automatiquement. On peut également lui demander certaines actions.

# Ressources

Pour diversifier mes compétences, le bot stocke des données dans :
- Des fichiers pickle (paramètres du bot + la régression linéaire)
- Un fichier texte (les identifiants de certains channels ou comptes Discord)
- Une BDD SQL avec sqlite3, sqlalchemy et posgresql (les data league of legends) 
- Json

Les visuels sont réalisés avec :
- Matplotlib
- Seaborn
- Plotly express / Plotly.graph_objects
- Pygal
- Pillow
- Images crées par moi-même

Autres librairies utilisées :
- Pandas
- Numpy
- Scikit-learn et skicit-image pour la régression linéaire et l'utilisation de carte League of Legends
- Discord, Discord.ext, Discord_slash et Asyncio pour le fonctionnement du bot
- RiotWatcher pour les requêtes à l'API de Riot Games
- Requests / urllib / mwclient
- Datetime
- os

etc...

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
  <img width="500" height="1000" src="https://github.com/Tomlora/MarinSlash/blob/main/synthese.jpg?raw=true">
</p>

-------------
 <p align="center">
  <img width="1000" height="500" src="https://media.discordapp.net/attachments/507539591473922068/1013078052533698671/resume_perso.png?width=1244&height=670">
</p>


### Records

- Les records des joueurs trackés sont enregistrés. Il peut donc retrouver ses différents records et sur quel champion il l'a obtenu par rapport aux autres joueurs du tracker
- Il peut également voir ses propres records personnels, sans les comparer aux autres.

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

Où étais-je à 15 minutes de jeu sur la carte ? 

 <p align="center">
  <img width="480" height="390" src="https://cdn.discordapp.com/attachments/534111278923513887/962433559077982278/plot.png">
</p>

Comment notre équipe a évolué au cours de la partie ?

A quel moment ai-je utilisé mon item ?

__Le bot peut répondre à toutes ces questions.__

## Nouveau patch

League of Legends est un jeu qui est mis à jour toutes les deux semaines (Nouveau contenu, équilibrage du contenu existant...)
Le bot est capable de détecter un nouveau patch, et de partager un résumé en image

 <p align="center">
  <img width="480" height="390" src="https://github.com/Tomlora/MarinSlash/blob/main/recap.png?raw=true">
</p>


## Teamfight Tactics

- En attente de l'accord de Riot Games pour la pérennité de l'outil..

## Automatisation

### Rapport de partie / Tracker


- Construis un rapport de chaque partie avec les stats principales
- Un joueur peut ajouter/retirer son compte au tracker

## Competitif pro

### Statistiques

- Le bot peut afficher les statistiques principales des joueurs pros dans toutes les compétitions gérées par Riot Games. (Corée, Chine, USA, Europe, Amérique du Nord...)
- Lister les joueurs pros de chaque équipe
- Affiche les durées de contrat de chaque joueur

### Alarme

- Le bot peut servir d'alarme pour les joueurs qui souhaitent suivre certaines compétitions. En effet, via un calendrier, le bot peut annoncer lorsqu'une game pro commence.

## Projet 2 : Musique

Le bot peut être un DJ dans un salon vocal Discord.


## Projet 3 : Summoners Wars

En utilisant un fichier json généré par Summoners Wars, le bot peut afficher divers informations sur son compte ou sur les contenus de guilde.


## Projet 4 : Twitch

Détermine dans un tracker si une personne a lancé son stream twitch, et sur quel jeu.


## Projet 5 : Twitter

Suit les tweets de certains journalistes pour avoir l'information rapidement.





