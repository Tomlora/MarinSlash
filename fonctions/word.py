import difflib

def suggestion_word(mot: str, liste_mots : list):
    suggestion = ', '.join(difflib.get_close_matches(mot, liste_mots))
    return suggestion    