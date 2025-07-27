import difflib

def suggestion_word(keyword: str,
                    liste_mots : list,
                    n : int = 3,
                    cutoff : float = 0.6):
    suggestion = ', '.join(difflib.get_close_matches(keyword, liste_mots, n=n, cutoff=cutoff))
    return suggestion    