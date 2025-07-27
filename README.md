# MarinSlash
__Bot discord affichant des statistiques (League of Legends, TFT, Twitch, Summoners Wars, Twitter, Github ...) sous forme visuel__

Le bot collecte, traite et réutilise les données automatiquement et en continu. On peut également lui demander certaines actions.

__Disclaimer : C'est un projet hobby, qui a été developpé pour apprendre Python. Le code peut donc être simplifié__

# Ressources

Pour diversifier mes compétences, le bot stocke des données dans :
- Des fichiers pickle (paramètres du bot + la régression linéaire)
- Un fichier texte (les identifiants de certains channels ou comptes Discord)
- Une BDD SQL avec sqlite3, sqlalchemy et posgresql (Data des différents jeux) 
- Json

****

Les visuels sont réalisés avec :
- Matplotlib
- Seaborn
- Plotly express / Plotly.graph_objects
- Pygal
- Pillow
- Images créees par moi-même

**** 
Autres librairies utilisées :
- Pandas
- Numpy
- Scikit-learn et skicit-image pour la régression linéaire et l'utilisation de carte League of Legends
- Discord, Discord-interactions et Asyncio pour le fonctionnement du bot
- RiotWatcher pour les requêtes à l'API de Riot Games
- Requests / urllib / mwclient ou Aiohttp
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
Image générée<b>du recap de la game</b> : 
 <br>
 <img width="1100" height="650" src="https://github.com/Tomlora/MarinSlash/blob/master/synthese_detaille.png?raw=true">
  <br>
</p>


<p align="center">
 Recap complet sur Discord :
 <br>
 <br>
 <br>
  <img src="https://github.com/Tomlora/MarinSlash/blob/master/synthese3.png?raw=true" width="45%" style="margin-right: 10px;">
  <img src="https://github.com/Tomlora/MarinSlash/blob/master/synthese7.png?raw=true" width="45%">
</p>

<p align="center">
  Détection des joueurs <b>débutants / OTP / important ou faible winrate</b> :
  <br>
  <img src="https://raw.githubusercontent.com/Tomlora/MarinSlash/main/otp.png" width="50%">
</p>
 

Ce recap est personnalisable, c'est-à-dire qu'il y a différents modules qui peuvent être affichés ou non, comme les insights (les bons/mauvais points d'une partie) ou les succès (des challenges crées par Riot Games).

#### Detections de joueurs pro 

<p align="center">
 <br>
  <img width="400" height="160" src="https://raw.githubusercontent.com/Tomlora/MarinSlash/main/detection_pros.png">
 <br>
 </p>

-------------

### Records

- Les records des joueurs trackés sont enregistrés. Il peut donc retrouver ses différents records et sur quel champion il l'a obtenu par rapport aux autres joueurs du tracker
- Il peut également voir ses propres records personnels, sans les comparer aux autres.

<p align="center">
 <br>
  <img width="500" height="600" src="https://github.com/Tomlora/MarinSlash/blob/master/records.png?raw=true">
 <br>
 </p>

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

 <p align="center">
  <img width="700" height="400" src="https://github.com/Tomlora/MarinSlash/blob/master/vision.png?raw=true">
  <img width="1000" height="500" src="https://github.com/Tomlora/MarinSlash/blob/master/gold_team.png?raw=true">
</p>

Ai-je amassé beaucoup de gold, me permettant d'être plus forts, par rapport aux autres ?

Analyse de la position :  

<p align="center">
  <img src="https://raw.githubusercontent.com/Tomlora/MarinSlash/main/position.png" width="45%" style="margin-right: 10px;">
  <img src="https://raw.githubusercontent.com/Tomlora/MarinSlash/main/position_kills.png" width="45%">
</p>



__Le bot peut répondre à toutes ces questions.__

## Nouveau patch

League of Legends est un jeu qui est mis à jour toutes les deux semaines (Nouveau contenu, équilibrage du contenu existant...)
Le bot est capable de détecter un nouveau patch, et de partager un résumé en image


****

## Teamfight Tactics

 <p align="center">
  <img width="400" height="800" src="https://raw.githubusercontent.com/Tomlora/MarinSlash/main/tft.png">
</p>

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

****
## Projet 2 : Musique

Le bot peut être un DJ dans un salon vocal Discord.

****

## Projet 3 : Twitch

Détermine dans un tracker si une personne a lancé son stream twitch, et sur quel jeu.

****
## Projet 4 : Finance

Le bot peut montrer divers informations sur des entreprises, des ETF ou des actualités boursières. 
Il peut aider au calcul du prix optimal d'une action en fonction de nos attentes dans le futur.

A l'avenir, permettra de calculer les croisements de moyenne mobile 12j/2j qui sont une autre technique d'analyse de bourse.


