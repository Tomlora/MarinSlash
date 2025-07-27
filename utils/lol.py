from fonctions.gestion_bdd import lire_bdd_perso 



def label_tier(x):
    dict_chg_tier = lire_bdd_perso('SELECT * from data_rank', index_col='nom')\
                                                                                    .T\
                                                                                        .to_dict()['tier']
                                                                                        
    for key, value in dict_chg_tier.items():
        try:
            dict_chg_tier[key] = int(value)    
        except:
            continue   
    return dict_chg_tier.get(x,0)

def label_rank(x):
    dict_chg_rank = {'En placement': 0,
                    'IV': 1,
                    'III': 2,
                    'II': 3,
                    'I': 4}
    return dict_chg_rank[x]


label_ward = {'YELLOW TRINKET': 1,
                'UNDEFINED': 2,
                'CONTROL_WARD': 3,
                'SIGHT_WARD': 4,
                'BLUE_TRINKET': 5}



dict_rankid = lire_bdd_perso('SELECT * from data_rank_soloq', index_col='rank')\
                                                                                    .T\
                                                                                        .to_dict()['id']


dict_rankid_challenges = {"NONE": 0,
                              "IRON": 1,
                              "BRONZE": 2,
                              "SILVER": 3,
                              "GOLD": 4,
                              "PLATINUM": 5,
                              "DIAMOND": 6,
                              "MASTER": 7,
                              "GRANDMASTER": 8,
                              "CHALLENGER": 9
                              }



elo_lp = {'IRON': 0,
          'BRONZE': 1,
          'SILVER': 2,
          'GOLD': 3,
          'PLATINUM': 4,
           'EMERALD' : 5,
          'DIAMOND': 6,
          'MASTER': 7,
          'GRANDMASTER': 8,
          'CHALLENGER': 9,
          'FIRST_GAME': 0}



dict_points = {41: [11, -19],
               42: [12, -18],
               43: [13, -17],
               44: [14, -16],
               45: [15, -15],
               46: [16, -15],
               47: [17, -15],
               48: [18, -15],
               49: [19, -15],
               50: [20, -15],
               51: [21, -15],
               52: [22, -15],
               53: [23, -15],
               54: [24, -15],
               55: [25, -15],
               56: [26, -14],
               57: [27, -13],
               58: [28, -12],
               59: [29, -11]}

dict_id_q = lire_bdd_perso('SELECT * from data_queue', index_col='identifiant')\
                                                                                    .T\
                                                                                        .to_dict()['mode']