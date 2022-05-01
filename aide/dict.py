nouvelle_campagne = {
    "responsable_de_campagne": "Jeanne d'Arc",
    "nom_de_campagne": "Campagne nous aimons les chiens",
    "date_de_début": "01/01/2020",
    "influenceurs_importants": ["@MonAmourDeChien", "@MeilleuresFriandisesPourChiens"]
}

print(nouvelle_campagne["responsable_de_campagne"]) #resultat = jeanne d'arc

print(nouvelle_campagne)
print(nouvelle_campagne['influenceurs_importants'][0])

nouvelle_campagne["test"] = ["a", "b"]
print(nouvelle_campagne["test"][0])
print(nouvelle_campagne)
