import pandas as pd
import numpy as np
from fonctions.gestion_bdd import lire_bdd_perso


class Rune():
    def __init__(self, data_json):
        self.data_json = data_json
        self.player_runes = {}

    async def prepare_data(self):
        for rune in self.data_json['runes']:
            first_sub = 0
            first_sub_value = 0
            first_sub_grinded_value = 0
            second_sub = 0
            second_sub_value = 0
            second_sub_grinded_value = 0
            third_sub = 0
            third_sub_value = 0
            third_sub_grinded_value = 0
            fourth_sub = 0
            fourth_sub_value = 0
            fourth_sub_grinded_value = 0
            first_gemme_bool = 0
            first_sub_grinded_value = 0
            second_gemme_bool = 0
            second_sub_grinded_value = 0
            third_gemme_bool = 0
            third_sub_grinded_value = 0
            fourth_gemme_bool = 0
            fourth_sub_grinded_value = 0

            rune_id = rune['rune_id']
            rune_set = rune['set_id']
            rune_slot = rune['slot_no']
            rune_equiped = rune['occupied_id']
            stars = rune['class']
            level = rune['upgrade_curr']
            efficiency = 0
            max_efficiency = 0
            max_efficiency_reachable = 0
            gain = 0
            main_type = rune['pri_eff'][0]
            main_value = rune['pri_eff'][1]
            innate_type = rune['prefix_eff'][0]
            innate_value = rune['prefix_eff'][1]

            if level > 2:
                first_sub = rune['sec_eff'][0][0]
                first_sub_value = rune['sec_eff'][0][1]
                first_gemme_bool = rune['sec_eff'][0][2]
                first_sub_grinded_value = rune['sec_eff'][0][3]
            if level > 5:
                second_sub = rune['sec_eff'][1][0]
                second_sub_value = rune['sec_eff'][1][1]
                second_gemme_bool = rune['sec_eff'][1][2]
                second_sub_grinded_value = rune['sec_eff'][1][3]
            if level > 8:
                third_sub = rune['sec_eff'][2][0]
                third_sub_value = rune['sec_eff'][2][1]
                third_gemme_bool = rune['sec_eff'][2][2]
                third_sub_grinded_value = rune['sec_eff'][2][3]
            if level > 11:
                fourth_sub = rune['sec_eff'][3][0]
                fourth_sub_value = rune['sec_eff'][3][1]
                fourth_gemme_bool = rune['sec_eff'][3][2]
                fourth_sub_grinded_value = rune['sec_eff'][3][3]

            try:
                self.player_runes[rune_id] = [rune_set, rune_slot, rune_equiped, stars, level, efficiency, max_efficiency,
                                              max_efficiency_reachable, gain, main_type, main_value, innate_type, innate_value,
                                              first_sub, first_sub_value, first_gemme_bool,  first_sub_grinded_value, second_sub, second_sub_value, second_gemme_bool,
                                              second_sub_grinded_value, third_sub, third_sub_value, third_gemme_bool, third_sub_grinded_value, fourth_sub,
                                              fourth_sub_value, fourth_gemme_bool, fourth_sub_grinded_value]
            except:
                print(f'Erreur : {rune_id}')

        # Rune équipée
        for unit in self.data_json['unit_list']:
            for stat in unit:
                if stat == "runes":
                    for rune in unit[stat]:
                        first_sub = 0
                        first_sub_value = 0
                        first_sub_grinded_value = 0
                        second_sub = 0
                        second_sub_value = 0
                        second_sub_grinded_value = 0
                        third_sub = 0
                        third_sub_value = 0
                        third_sub_grinded_value = 0
                        fourth_sub = 0
                        fourth_sub_value = 0
                        fourth_sub_grinded_value = 0

                        rune_id = rune['rune_id']
                        rune_set = rune['set_id']
                        rune_slot = rune['slot_no']
                        rune_equiped = rune['occupied_id']
                        stars = rune['class']
                        level = rune['upgrade_curr']
                        efficiency = 0
                        max_efficiency = 0
                        max_efficiency_reachable = 0
                        gain = 0
                        main_type = rune['pri_eff'][0]
                        main_value = rune['pri_eff'][1]
                        innate_type = rune['prefix_eff'][0]
                        innate_value = rune['prefix_eff'][1]
                        # rank = rune['extra']
                        if level > 2:
                            first_sub = rune['sec_eff'][0][0]
                            first_sub_value = rune['sec_eff'][0][1]
                            first_gemme_bool = rune['sec_eff'][0][2]
                            first_sub_grinded_value = rune['sec_eff'][0][3]
                        if level > 5:
                            second_sub = rune['sec_eff'][1][0]
                            second_sub_value = rune['sec_eff'][1][1]
                            second_gemme_bool = rune['sec_eff'][1][2]
                            second_sub_grinded_value = rune['sec_eff'][1][3]
                        if level > 8:
                            third_sub = rune['sec_eff'][2][0]
                            third_sub_value = rune['sec_eff'][2][1]
                            third_gemme_bool = rune['sec_eff'][2][2]
                            third_sub_grinded_value = rune['sec_eff'][2][3]
                        if level > 11:
                            fourth_sub = rune['sec_eff'][3][0]
                            fourth_sub_value = rune['sec_eff'][3][1]
                            fourth_gemme_bool = rune['sec_eff'][3][2]
                            fourth_sub_grinded_value = rune['sec_eff'][3][3]

                        self.player_runes[rune_id] = [rune_set, rune_slot, rune_equiped, stars, level, efficiency, max_efficiency,
                                                      max_efficiency_reachable, gain, main_type, main_value, innate_type, innate_value,
                                                      first_sub, first_sub_value, first_gemme_bool, first_sub_grinded_value, second_sub, second_sub_value, second_gemme_bool,
                                                      second_sub_grinded_value, third_sub, third_sub_value, third_gemme_bool, third_sub_grinded_value, fourth_sub,
                                                      fourth_sub_value, fourth_gemme_bool, fourth_sub_grinded_value]

                # on crée un df avec la data

        self.data = pd.DataFrame.from_dict(self.player_runes, orient="index", columns=['rune_set', 'rune_slot', 'rune_equiped', 'stars', 'level', 'efficiency', 'max_efficiency', 'max_efficiency_reachable', 'gain', 'main_type', 'main_value', 'innate_type',
                                                                                       'innate_value', 'first_sub', 'first_sub_value', 'first_gemme_bool', 'first_sub_grinded_value', 'second_sub', 'second_sub_value', 'second_gemme_bool',
                                                                                       'second_sub_grinded_value', 'third_sub', 'third_sub_value', 'third_gemme_bool', 'third_sub_grinded_value', 'fourth_sub',
                                                                                       'fourth_sub_value', 'fourth_gemme_bool', 'fourth_sub_grinded_value'])

        # # Map des sets

        self.set = {1: "Energy", 2: "Guard", 3: "Swift", 4: "Blade", 5: "Rage",
                    6: "Focus", 7: "Endure", 8: "Fatal", 10: "Despair", 11: "Vampire", 13: "Violent",
                    14: "Nemesis", 15: "Will", 16: "Shield", 17: "Revenge", 18: "Destroy", 19: "Fight",
                    20: "Determination", 21: "Enhance", 22: "Accuracy", 23: "Tolerance", 99: "Immemorial"}

        self.data['rune_set'] = self.data['rune_set'].map(self.set)

        # # Efficiency

        # Valeur max
        sub = {1: (375 * 5) * 2,  # PV flat
               2: 8 * 5,  # PV%
               3: (20 * 5) * 2,  # ATQ FLAT
               4: 8 * 5,  # ATQ%
               5: (20 * 5) * 2,  # DEF FLAT
               6: 8 * 5,  # DEF %
               8: 6 * 5,  # SPD
               9: 6 * 5,  # CRIT
               10: 7 * 5,  # DCC
               11: 8 * 5,  # RES
               12: 8 * 5}  # ACC

        # On map les valeurs max
        self.data['first_sub_value_max'] = self.data['first_sub'].map(sub)
        self.data['second_sub_value_max'] = self.data['second_sub'].map(sub)
        self.data['third_sub_value_max'] = self.data['third_sub'].map(sub)
        self.data['fourth_sub_value_max'] = self.data['fourth_sub'].map(sub)
        self.data['innate_value_max'] = self.data['innate_type'].replace(sub)

        # Value des runes du joueur ( stats de base + meule )

        self.data['first_sub_value_total'] = (
            self.data['first_sub_value'] + self.data['first_sub_grinded_value'])
        self.data['second_sub_value_total'] = (
            self.data['second_sub_value'] + self.data['second_sub_grinded_value'])
        self.data['third_sub_value_total'] = (
            self.data['third_sub_value'] + self.data['third_sub_grinded_value'])
        self.data['fourth_sub_value_total'] = (
            self.data['fourth_sub_value'] + self.data['fourth_sub_grinded_value'])

        # calcul de l'efficiency (stat de la rune / stat max possible)

        self.data['efficiency'] = np.where(self.data['innate_type'] != 0, round(((1+self.data['innate_value'] / self.data['innate_value_max']
                                                                                + self.data['first_sub_value_total'] / self.data['first_sub_value_max']
                                                                                + self.data['second_sub_value_total'] / self.data['second_sub_value_max']
                                                                                + self.data['third_sub_value_total'] / self.data['third_sub_value_max']
                                                                                + self.data['fourth_sub_value_total'] / self.data['fourth_sub_value_max'])
                                                                                 / 2.8)*100, 2),
                                           round(((1 + self.data['first_sub_value_total'] / self.data['first_sub_value_max']
                                                   + self.data['second_sub_value_total'] / self.data['second_sub_value_max']
                                                   + self.data['third_sub_value_total'] / self.data['third_sub_value_max']
                                                   + self.data['fourth_sub_value_total'] / self.data['fourth_sub_value_max'])
                                                  / 2.8)*100, 2))

        self.data_spd = self.data.copy()

    async def scoring_rune(self, category_selected, coef_set):
        self.data_r = self.data[['rune_set', 'efficiency']]

        self.data_r['efficiency_binned'] = pd.cut(
            self.data_r['efficiency'], bins=(100, 110, 119.99, 139.99), right=False)

        # en dessous de 100, renvoie null, on les enlève.

        self.data_r.dropna(inplace=True)

        result = self.data_r.groupby(['rune_set', 'efficiency_binned']).count()
        # pas besoin d'un multiindex
        result.reset_index(inplace=True)

        # palier
        palier_1 = result['efficiency_binned'].unique()[0]  # '[100.0, 110.0)'
        palier_2 = result['efficiency_binned'].unique()[1]  # '[110.0, 120.0)'
        palier_3 = result['efficiency_binned'].unique()[2]  # '[120.0, 130.0)'

        # poids des paliers

        palier = {palier_1: 1,
                  palier_2: 2,
                  palier_3: 3}

        result['factor'] = 0

        for key, value in palier.items():
            result['factor'] = np.where(
                result['efficiency_binned'] == key, value, result['factor'])

        result['points'] = result['efficiency'] * result['factor']

        # on sépare les dataset à mettre en évidence et les autres

        self.value_selected = result[result['rune_set'].isin(
            category_selected)]
        self.value_autres = result[~result['rune_set'].isin(category_selected)]

        self.value_selected.drop(['factor'], axis=1, inplace=True)

        # on ajoute les poids des sets

        for set in category_selected:
            self.value_selected['points'] = np.where(
                self.value_selected['rune_set'] == set, self.value_selected['points'] * coef_set[set], self.value_selected['points'])

        self.value_autres = self.value_autres.groupby(
            'efficiency_binned').sum()
        self.value_autres.reset_index(inplace=True)
        self.value_autres.insert(0, 'rune_set', 'Autre')
        self.value_autres.drop(['factor'], axis=1, inplace=True)

        # on regroupe

        df_value = pd.concat([self.value_selected, self.value_autres])

        # on replace pour plus de lisibilité

        df_value['efficiency_binned'] = df_value['efficiency_binned'].replace({palier_1: 100,
                                                                               palier_2: 110,
                                                                               palier_3: 120})

        self.score_r = df_value['points'].sum()

        # Calcul du TCD :

        self.tcd_value = df_value.pivot_table(
            df_value, 'rune_set', 'efficiency_binned', 'sum')['efficiency']
        # pas besoin du multiindex
        self.tcd_value.columns.name = "efficiency"
        self.tcd_value.index.name = 'Set'

        total_100 = self.tcd_value[100].sum()
        total_110 = self.tcd_value[110].sum()
        total_120 = self.tcd_value[120].sum()

        self.tcd_value.loc['Total'] = [total_100, total_110, total_120]

        return self.tcd_value, self.score_r

    async def scoring_spd(self, category_selected_spd, coef_set_spd):

        def detect_speed(df):
            for sub in ['first_sub', 'second_sub', 'third_sub', 'fourth_sub']:
                if df[sub] == 8:  # stat speed = 8
                    df['spd'] = df[f'{sub}_value_total']

            return df

        self.data_spd['spd'] = 0

        self.data_spd = self.data_spd.apply(detect_speed, axis=1)

        self.data_spd = self.data_spd[['rune_set', 'spd']]

        self.data_spd['spd_binned'] = pd.cut(
            self.data_spd['spd'], bins=(23, 26, 29, 32, 36, 40), right=False)

        self.data_spd.dropna(inplace=True)

        self.result_spd = self.data_spd.groupby(
            ['rune_set', 'spd_binned']).count()

        self.result_spd.reset_index(inplace=True)

        palier_1 = self.result_spd['spd_binned'].unique()[0]  # 23-26
        palier_2 = self.result_spd['spd_binned'].unique()[1]  # 26-29
        palier_3 = self.result_spd['spd_binned'].unique()[2]  # 29-32
        palier_4 = self.result_spd['spd_binned'].unique()[3]  # 32-36
        palier_5 = self.result_spd['spd_binned'].unique()[4]  # 36+

        palier_spd = {palier_1: 1,
                      palier_2: 2,
                      palier_3: 3,
                      palier_4: 4,
                      palier_5: 5}

        self.result_spd['factor_spd'] = 0

        for key, value in palier_spd.items():
            self.result_spd['factor_spd'] = np.where(
                self.result_spd['spd_binned'] == key, value, self.result_spd['factor_spd'])

        self.result_spd['points_spd'] = self.result_spd['spd'] * \
            self.result_spd['factor_spd']

        # on sépare les dataset à mettre en évidence et les autres

        self.value_selected_spd = self.result_spd[self.result_spd['rune_set'].isin(
            category_selected_spd)]
        self.value_autres_spd = self.result_spd[~self.result_spd['rune_set'].isin(
            category_selected_spd)]

        self.value_selected_spd.drop(['factor_spd'], axis=1, inplace=True)

        for set in category_selected_spd:
            self.value_selected_spd['points_spd'] = np.where(
                self.value_selected_spd['rune_set'] == set, self.value_selected_spd['points_spd'] * coef_set_spd[set], self.value_selected_spd['points_spd'])

        self.value_autres_spd = self.value_autres_spd.groupby(
            'spd_binned').sum()
        self.value_autres_spd.reset_index(inplace=True)
        self.value_autres_spd.insert(0, 'rune_set', 'Autre')
        self.value_autres_spd.drop(['factor_spd'], axis=1, inplace=True)

        self.df_value_spd = pd.concat(
            [self.value_selected_spd, self.value_autres_spd])

        # on replace pour plus de lisibilité

        self.df_value_spd['spd_binned'] = self.df_value_spd['spd_binned'].replace({palier_1: '23-26',
                                                                                   palier_2: '26-29',
                                                                                   palier_3: '29-32',
                                                                                   palier_4: '32-36',
                                                                                   palier_5: '36+'})

        self.score_spd = self.df_value_spd['points_spd'].sum()

        self.tcd_value_spd = self.df_value_spd.pivot_table(
            self.df_value_spd, 'rune_set', 'spd_binned', 'sum')['spd']

        # pas besoin du multiindex
        self.tcd_value_spd .columns.name = "spd"
        self.tcd_value_spd .index.name = 'Set'

        total_23_spd = self.tcd_value_spd['23-26'].sum()
        total_26_spd = self.tcd_value_spd['26-29'].sum()
        total_29_spd = self.tcd_value_spd['29-32'].sum()
        total_32_spd = self.tcd_value_spd['32-36'].sum()
        total_36_spd = self.tcd_value_spd['36+'].sum()

        self.tcd_value_spd .loc['Total'] = [
            total_23_spd, total_26_spd, total_29_spd, total_32_spd, total_36_spd]

        return self.tcd_value_spd, self.score_spd


dict_arte_type = {
    1: 'ELEMENT',
    2: 'ARCHETYPE',
}

dict_arte_effect = {
    200: {'name': 'EFFECT_ATK_LOST_HP', 'max': 14},
    201: {'name': 'EFFECT_DEF_LOST_HP', 'max': 14},
    202: {'name': 'EFFECT_SPD_LOST_HP', 'max': 14},
    203: {'name': 'EFFECT_SPD_INABILITY', 'max': 6},
    204: {'name': 'EFFECT_ATK', 'max': 5},
    205: {'name': 'EFFECT_DEF', 'max': 4},
    206: {'name': 'EFFECT_SPD', 'max': 6},
    207: {'name': 'EFFECT_CRIT_RATE', 'max': 6},
    208: {'name': 'EFFECT_COUNTER_DMG', 'max': 4},
    209: {'name': 'EFFECT_COOP_ATTACK_DMG', 'max': 4},
    210: {'name': 'EFFECT_BOMB_DMG', 'max': 4},
    211: {'name': 'EFFECT_REFLECT_DMG', 'max': 3},
    212: {'name': 'EFFECT_CRUSHING_HIT_DMG', 'max': 4},
    213: {'name': 'EFFECT_DMG_RECEIVED_INABILITY', 'max': 3},
    214: {'name': 'EFFECT_CRIT_DMG_RECEIVED', 'max': 4},
    215: {'name': 'EFFECT_LIFE_DRAIN', 'max': 8},
    216: {'name': 'EFFECT_HP_REVIVE', 'max': 6},
    217: {'name': 'EFFECT_ATB_REVIVE', 'max': 6},
    218: {'name': 'EFFECT_DMG_PCT_OF_HP', 'max': 0.3},
    219: {'name': 'EFFECT_DMG_PCT_OF_ATK', 'max': 4},
    220: {'name': 'EFFECT_DMG_PCT_OF_DEF', 'max': 4},
    221: {'name': 'EFFECT_DMG_PCT_OF_SPD', 'max': 40},
    222: {'name': 'EFFECT_CRIT_DMG_UP_ENEMY_HP_GOOD', 'max': 6},
    223: {'name': 'EFFECT_CRIT_DMG_UP_ENEMY_HP_BAD', 'max': 12},
    224: {'name': 'EFFECT_CRIT_DMG_SINGLE_TARGET', 'max': 4},
    300: {'name': 'EFFECT_DMG_TO_FIRE', 'max': 5},
    301: {'name': 'EFFECT_DMG_TO_WATER', 'max': 5},
    302: {'name': 'EFFECT_DMG_TO_WIND', 'max': 5},
    303: {'name': 'EFFECT_DMG_TO_LIGHT', 'max': 5},
    304: {'name': 'EFFECT_DMG_TO_DARK', 'max': 5},
    305: {'name': 'EFFECT_DMG_FROM_FIRE', 'max': 6},
    306: {'name': 'EFFECT_DMG_FROM_WATER', 'max': 6},
    307: {'name': 'EFFECT_DMG_FROM_WIND', 'max': 6},
    308: {'name': 'EFFECT_DMG_FROM_LIGHT', 'max': 6},
    309: {'name': 'EFFECT_DMG_FROM_DARK', 'max': 6},
    400: {'name': 'EFFECT_SK1_CRIT_DMG', 'max': 6},
    401: {'name': 'EFFECT_SK2_CRIT_DMG', 'max': 6},
    402: {'name': 'EFFECT_SK3_CRIT_DMG', 'max': 6},
    403: {'name': 'EFFECT_SK4_CRIT_DMG', 'max': 6},
    404: {'name': 'EFFECT_SK1_RECOVERY', 'max': 6},
    405: {'name': 'EFFECT_SK2_RECOVERY', 'max': 6},
    406: {'name': 'EFFECT_SK3_RECOVERY', 'max': 6},
    407: {'name': 'EFFECT_SK1_ACCURACY', 'max': 6},
    408: {'name': 'EFFECT_SK2_ACCURACY', 'max': 6},
    409: {'name': 'EFFECT_SK3_ACCURACY', 'max': 6},
}

dict_arte_archetype = {
    0: 'ARCHETYPE_NONE',
    1: 'ARCHETYPE_ATTACK',
    2: 'ARCHETYPE_DEFENSE',
    3: 'ARCHETYPE_HP',
    4: 'ARCHETYPE_SUPPORT',
    5: 'ARCHETYPE_MATERIAL'
}

dict_arte_main_stat = {
    100: 'HP',
    101: 'ATK',
    102: 'DEF',
}


class Artefact():
    def __init__(self, data_json):
        self.data_json = data_json
        self.player_arte = {}

    async def prepare_data(self):
        for arte in self.data_json['artifacts']:
            first_sub = 0
            first_sub_value = 0
            second_sub = 0
            second_sub_value = 0
            third_sub = 0
            third_sub_value = 0
            fourth_sub = 0
            fourth_sub_value = 0

            arte_id = arte['rid']
            arte_type = arte['type']
            arte_attribut = arte['attribute']
            arte_equiped = arte['occupied_id']
            level = arte['level']
            efficiency = 0

            main_type = arte['pri_effect'][0]
            main_value = arte['pri_effect'][1]

            if level > 2:
                first_sub = arte['sec_effects'][0][0]
                first_sub_value = arte['sec_effects'][0][1]

            if level > 5:
                second_sub = arte['sec_effects'][1][0]
                second_sub_value = arte['sec_effects'][1][1]

            if level > 8:
                third_sub = arte['sec_effects'][2][0]
                third_sub_value = arte['sec_effects'][2][1]

            if level > 11:
                fourth_sub = arte['sec_effects'][3][0]
                fourth_sub_value = arte['sec_effects'][3][1]

            self.player_arte[arte_id] = [arte_type, arte_attribut, arte_equiped, level, efficiency,
                                         main_type, main_value,
                                         first_sub, first_sub_value, second_sub, second_sub_value, third_sub, third_sub_value,
                                         fourth_sub, fourth_sub_value]

        # arte équipée
        for unit in self.data_json['unit_list']:
            for stat in unit:
                if stat == "artifacts":
                    for arte in unit[stat]:
                        first_sub = 0
                        first_sub_value = 0

                        second_sub = 0
                        second_sub_value = 0

                        third_sub = 0
                        third_sub_value = 0

                        fourth_sub = 0
                        fourth_sub_value = 0

                        arte_id = arte['rid']

                        arte_type = arte['type']
                        arte_attribut = arte['attribute']
                        arte_equiped = arte['occupied_id']

                        level = arte['level']
                        efficiency = 0

                        main_type = arte['pri_effect'][0]
                        main_value = arte['pri_effect'][1]

                        # rank = arte['extra']
                        if level > 2:
                            first_sub = arte['sec_effects'][0][0]
                            first_sub_value = arte['sec_effects'][0][1]

                        if level > 5:
                            second_sub = arte['sec_effects'][1][0]
                            second_sub_value = arte['sec_effects'][1][1]

                        if level > 8:
                            third_sub = arte['sec_effects'][2][0]
                            third_sub_value = arte['sec_effects'][2][1]

                        if level > 11:
                            fourth_sub = arte['sec_effects'][3][0]
                            fourth_sub_value = arte['sec_effects'][3][1]

                        self.player_arte[arte_id] = [arte_type, arte_attribut, arte_equiped, level, efficiency,
                                                     main_type, main_value,
                                                     first_sub, first_sub_value, second_sub, second_sub_value,
                                                     third_sub, third_sub_value, fourth_sub, fourth_sub_value]

        self.data_a = pd.DataFrame.from_dict(self.player_arte, orient="index", columns=['arte_type', 'arte_attribut', 'arte_equiped', 'level', 'efficiency', 'main_type', 'main_value',
                                                                                        'first_sub', 'first_sub_value',  'second_sub', 'second_sub_value',
                                                                                        'third_sub', 'third_sub_value',
                                                                                        'fourth_sub', 'fourth_sub_value'])

        # on prend que les arté montés

        self.data_a = self.data_a[self.data_a['level'] == 15]

        # on map les identifiants par les mots pour plus de lisibilités

        self.data_a['arte_type'] = self.data_a['arte_type'].map(dict_arte_type)
        self.data_a['arte_attribut'] = self.data_a['arte_attribut'].map(
            dict_arte_archetype)
        self.data_a['main_type'] = self.data_a['main_type'].map(
            dict_arte_main_stat)

        def value_max(x):
            return dict_arte_effect[x]['max']  # first proc + 4 upgrades

        def replace_effect(x):
            return dict_arte_effect[x]['name']

        for c in ['first_sub', 'second_sub', 'third_sub', 'fourth_sub']:
            self.data_a[f'{c}_value_max'] = self.data_a[c].apply(value_max)
            self.data_a[c] = self.data_a[c].apply(replace_effect)

        self.data_a['efficiency'] = round(((self.data_a['first_sub_value'] / self.data_a['first_sub_value_max']
                                            + self.data_a['second_sub_value'] /
                                            self.data_a['second_sub_value_max']
                                            + self.data_a['third_sub_value'] /
                                            self.data_a['third_sub_value_max']
                                            + self.data_a['fourth_sub_value'] / self.data_a['fourth_sub_value_max'])
                                           / 8)*100, 2)

    async def scoring_arte(self):
        self.data_eff = self.data_a[['efficiency', 'arte_type', 'main_type']]

        self.data_eff['eff_binned'] = pd.cut(
            self.data_eff['efficiency'], bins=(80, 85, 90, 95, 100, 120), right=False)

        self.data_eff.dropna(inplace=True)

        self.data_eff = self.data_eff.groupby(
            ['eff_binned', 'arte_type', 'main_type']).count()

        self.data_eff.reset_index(inplace=True)

        palier_1 = self.data_eff['eff_binned'].unique()[0]  # 80-85
        palier_2 = self.data_eff['eff_binned'].unique()[1]  # 85-90
        palier_3 = self.data_eff['eff_binned'].unique()[2]  # 90-95
        palier_4 = self.data_eff['eff_binned'].unique()[3]  # 95-100
        palier_5 = self.data_eff['eff_binned'].unique()[4]  # 100+

        palier_arte = {palier_1: 1,
                       palier_2: 2,
                       palier_3: 3,
                       palier_4: 4,
                       palier_5: 5}

        self.data_eff['factor'] = 0

        for key, value in palier_arte.items():
            self.data_eff['factor'] = np.where(
                self.data_eff['eff_binned'] == key, value, self.data_eff['factor'])

        self.data_eff['points'] = self.data_eff['efficiency'] * \
            self.data_eff['factor']

        self.data_eff.drop(['factor'], axis=1, inplace=True)

        self.data_eff['eff_binned'] = self.data_eff['eff_binned'].replace({palier_1: '80',
                                                                           palier_2: '85',
                                                                           palier_3: '90',
                                                                           palier_4: '95',
                                                                           palier_5: '100+'})

        self.score_a = self.data_eff['points'].sum()

        # Calcul du TCD :

        self.tcd_arte = self.data_eff.pivot_table(
            self.data_eff, ['arte_type', 'main_type'], 'eff_binned', 'sum')['efficiency']
        # pas besoin du multiindex
        self.tcd_arte.columns.name = "efficiency"
        self.tcd_arte.index.name = 'Artefact'

        self.tcd_arte.reset_index(inplace=True)
        self.tcd_arte.set_index('arte_type', inplace=True)

        self.tcd_arte.rename(columns={'main_type': 'type'}, inplace=True)

        total_80 = self.tcd_arte['80'].sum()
        total_85 = self.tcd_arte['85'].sum()
        total_90 = self.tcd_arte['90'].sum()
        total_95 = self.tcd_arte['95'].sum()
        total_100 = self.tcd_arte['100+'].sum()

        self.tcd_arte.loc['Total'] = [' ', total_80,
                                      total_85, total_90, total_95, total_100]

        return self.tcd_arte, self.score_a


async def comparaison(guilde_id):  # à changer par guilde_id
    # Lire la BDD
    df_actuel = lire_bdd_perso(
        'SELECT * from sw_user, sw_score WHERE sw_user.id = sw_score.id', index_col='joueur')
    df_actuel = df_actuel.transpose()
    df_actuel.reset_index(inplace=True)
    df_actuel.drop(['id'], axis=1, inplace=True)

    # On regroupe les scores max de tous les joueurs enregistrés
    df_max = df_actuel.groupby('joueur').max()

    # On trie du plus grand au plus petit
    df_max['rank'] = df_max['score'].rank(ascending=False, method='min')

    # Nb joueurs
    size_general = len(df_max)

    # Score moyen
    avg_score_general = int(round(df_max['score'].mean(), 0))

    # Meilleur score
    max_general = int(df_max['score'].max())

    # On refait les mêmes étapes pour la guilde Endless
    df_guilde = df_actuel[df_actuel['guilde_id'] == guilde_id]
    # df_guilde = df_actuel[df_actuel['guilde'] == guilde]
    df_guilde_max = df_guilde.groupby('joueur').max()
    size_guilde = len(df_guilde_max)
    avg_score_guilde = int(round(df_guilde_max['score'].mean(), 0))
    max_guilde = int(df_guilde_max['score'].max())
    df_guilde_max['rank'] = df_guilde_max['score'].rank(
        ascending=False, method='min')

    return size_general, avg_score_general, max_general, size_guilde, avg_score_guilde, max_guilde, df_max, df_guilde_max
