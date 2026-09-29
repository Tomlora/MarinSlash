"""Duration-aware provisional calibration. No IO, no API or database calls.

All displayed contribution components are the actual inputs to aggregation.
The anchors are explicit heuristics, not measured historical distributions.
"""
from .scoring_curves import (
    rate_score, participation_score, survival_score, advantage_score,
    rate_reference, participation_reference, dimension_summary, fmt,
)


# Multipliers of the 30-minute *rate*, not of the total. Interpolate smoothly.
RATE_ANCHORS = {
    'damage': ((10, .50), (20, .70), (30, 1.), (40, 1.25), (60, 1.40)),
    'gold': ((10, .75), (20, .90), (30, 1.), (40, 1.08), (60, 1.12)),
    'cs': ((10, .85), (20, .95), (30, 1.), (40, .95), (60, .85)),
    'vision': ((10, .55), (20, .75), (30, 1.), (40, 1.15), (60, 1.25)),
    'utility': ((10, .50), (20, .70), (30, 1.), (40, 1.20), (60, 1.35)),
    'cc': ((10, .70), (20, .85), (30, 1.), (40, 1.10), (60, 1.15)),
    'deaths': ((10, .70), (20, .85), (30, 1.), (40, 1.10), (60, 1.15)),
}


def duration_factor(kind, minutes):
    anchors = RATE_ANCHORS[kind]
    if minutes <= anchors[0][0]:
        return anchors[0][1]
    for (left, a), (right, b) in zip(anchors, anchors[1:]):
        if minutes <= right:
            return a + (b-a)*(minutes-left)/(right-left)
    return anchors[-1][1]


def champion_key(name):
    return name.lower().replace(' ', '').replace("'", '').replace('.', '')


# Applicability is determined before looking at the observed value. A real zero
# on an applicable skill stays zero. Unknown tank supports use CC only.
ALLY_UTILITY = {
    'alistar', 'bard', 'ivern', 'janna', 'karma', 'kayle', 'lulu', 'lux',
    'milio', 'morgana', 'nami', 'nidalee', 'orianna', 'rakan', 'renata',
    'senna', 'seraphine', 'shen', 'sona', 'soraka', 'taric', 'thresh', 'yuumi',
}
NO_CC_UTILITY = {'kayle', 'nidalee'}


def utility_kind(m):
    key = champion_key(m.champion)
    primary = (m.role == 'SUPPORT' and m.profile in ('TANK', 'SUPPORT_UTILITY')) or key == 'ivern'
    hybrid = key in ALLY_UTILITY and m.role == 'SUPPORT'
    return 'primary' if primary else 'hybrid' if hybrid else None


def references(m):
    from .scoring import ROLE_BASELINES
    b = ROLE_BASELINES[m.role_enum]
    t = m.game_minutes
    kda_adjustment = .85 if m.profile in ('TANK', 'FIGHTER') else 1.
    return {
        'damage': b.damage_per_min[0]*m.dpm_mult*duration_factor('damage', t),
        'gold': b.gold_per_min[0]*m.gpm_mult*duration_factor('gold', t),
        'cs': b.cs_per_min[0]*m.cs_mult*duration_factor('cs', t),
        'vision': b.vision_score_per_min[0]*m.vision_mult*duration_factor('vision', t),
        'kp': min(.9, b.kp[0]*m.kp_mult),
        'kda': b.kda[0]*kda_adjustment,
        'deaths': b.deaths[0]/30*t*duration_factor('deaths', t)*
                  (1.15 if m.profile == 'TANK' else 1.),
    }


def compute_utility(m):
    m.utility_available = False
    m.utility_score = 5.
    m.utility_parts = []
    kind = utility_kind(m)
    if not kind:
        return
    key = champion_key(m.champion)
    has_ally_utility = key in ALLY_UTILITY or m.profile == 'SUPPORT_UTILITY'
    candidates = []
    if has_ally_utility:
        healing = None if m.ally_healing is None or m.ally_shielding is None else m.ally_healing+m.ally_shielding
        ref = (400 if m.profile == 'SUPPORT_UTILITY' or key == 'ivern' else 100)*duration_factor('utility', m.game_minutes)
        candidates.append(('Soins et boucliers aux alliés', healing, ref, .7))
    if key not in NO_CC_UTILITY:
        ref = (1.5 if m.profile == 'TANK' else .6)*duration_factor('cc', m.game_minutes)
        candidates.append(('Contrôles (secondes)', m.cc_seconds, ref, .3 if has_ally_utility else 1.))
    available = sum(weight for _, value, _, weight in candidates if value is not None)
    for label, value, ref, weight in candidates:
        m.utility_parts.append(dict(label=label, value=value, reference=ref,
                                    weight=weight/available if value is not None and available else 0.,
                                    score=rate_score('utility', value/m.game_minutes, ref) if value is not None else None))
    if available:
        m.utility_available = True
        m.utility_score = sum(p['score']*p['weight'] for p in m.utility_parts if p['score'] is not None)


def statistical_score(m):
    from .scoring import ROLE_BASELINES, ROLE_WEIGHTS, calculate_z_score
    if not m.scoring_supported:
        m.zscore_score = 5.
        return
    refs = references(m)
    b = ROLE_BASELINES[m.role_enum]
    weights = dict(ROLE_WEIGHTS[m.role_enum])
    # Share metrics duplicate absolute production and are composition-sensitive.
    weights['damage_share'] = weights['damage_taken_share'] = 0.
    if utility_kind(m) == 'primary':
        weights['damage_per_min'] = 0.
    parts, _ = build_parts(m)
    inputs = (
        ('kda', 'z_kda', m.kda, refs['kda'], b.kda),
        ('cs_per_min', 'z_cs_per_min', m.cs_per_min, refs['cs'], b.cs_per_min),
        ('damage_per_min', 'z_damage_per_min', m.damage_per_min, refs['damage'], b.damage_per_min),
        ('gold_per_min', 'z_gold_per_min', m.gold_per_min, refs['gold'], b.gold_per_min),
        ('vision_score_per_min', 'z_vision_per_min', m.vision_per_min, refs['vision'], b.vision_score_per_min),
        ('kp', 'z_kp', m.kp, refs['kp'], b.kp),
    )
    # Legacy z fields remain diagnostic SQL columns, not the displayed score.
    for key, field, value, expected, baseline in inputs:
        z = calculate_z_score(value, expected, baseline[1]*expected/baseline[0])
        setattr(m, field, z)
    m.z_damage_share = m.z_damage_taken_share = 0.
    keys = {'kda':'kda', 'cs_per_min':'cs', 'damage_per_min':'damage',
            'gold_per_min':'gold', 'vision_score_per_min':'vision', 'kp':'kp'}
    selected = [(parts[part], weights[key]) for key,part in keys.items()
                if weights[key] > 0 and not parts[part]['neutral']]
    if utility_kind(m) and m.utility_available:
        selected.append((parts['utility'], .2 if utility_kind(m) == 'primary' else .1))
    total = sum(w for _,w in selected)
    m.zscore_score = sum(p['score']*w for p,w in selected)/total if total else 5.
    m.weighted_z = 0.  # no combined z-score in v5
    m.statistical_components = [dict(p, weight=w/total, points=p['score']*w/total)
                                for p,w in selected] if total else []


def build_parts(m):
    refs = references(m)
    t = m.game_minutes
    parts = {}

    def add(key, label, value, ref, *, observation=None, unit='', inverted=False, missing=False):
        if missing:
            score, reference = 5., 'Donnée absente ou aucune occasion pertinente : critère exclu ; aucun échec déduit.'
        elif key == 'deaths':
            score = survival_score(value, ref)
            reference = (f'Repères : aucune mort → 10/10 ; {fmt(ref/2)} morts → 8/10 ; '
                         f'{fmt(ref)} morts → 5/10. Moins de morts donne une meilleure note.')
        elif key in ('kp', 'epic', 'tower'):
            count = m.observed_team_kills if key == 'kp' else m.objective_opportunities.get(key, 0)
            minimum = 8 if key == 'kp' else 3
            score = participation_score(value, ref, count, minimum)
            reference = participation_reference(ref, count, minimum)
        elif key in ('gold15', 'cs15'):
            score, reference = advantage_score(value, ref), ''
        else:
            score, reference = rate_score(key, value, ref), rate_reference(key, ref, unit)
        parts[key] = dict(label=label, score=score, neutral=missing,
                          observation=observation or f'Ta valeur : {fmt(value,2)}{unit}.', reference=reference)
        return score

    m.kda_score = add('kda', 'Éliminations et assistances par mort', m.kda, refs['kda'],
                     observation=f'{m.kills} éliminations + {m.assists} assistances pour {m.deaths} morts : {fmt(m.kda,2)} actions par mort.'
                                 + (' Sans mort, le calcul divise par 1.' if m.deaths == 0 else ''))
    m.kp_score = add('kp', 'Participation aux éliminations', 100*m.kp, 100*refs['kp'], unit=' %',
                    missing=m.observed_team_kills == 0,
                    observation=f'{m.kills+m.assists} participations sur {m.observed_team_kills} éliminations de ton équipe ({fmt(100*m.kp)} %).')
    m.death_score = add('deaths', 'Survie', m.deaths, refs['deaths'], inverted=True,
                       observation=f'{m.deaths} morts en {fmt(t)} minutes. Les morts de tes alliés ne changent pas cette note.')
    m.dpg_score = add('dpg', 'Dégâts produits avec ton or', m.dpg, refs['damage']/refs['gold'],
                     missing=m.gold <= 0,
                     observation=f'{fmt(m.damage,0)} dégâts aux champions pour {fmt(m.gold,0)} or : {fmt(m.dpg,2)} dégâts/or.')
    m.cs_score = add('cs', 'Sbires et monstres par minute', m.cs_per_min, refs['cs'], unit='/min')
    m.gpm_relative_score = add('gold', 'Or gagné par minute', m.gold_per_min, refs['gold'], unit=' or/min')
    m.dpm_relative_score = add('damage', 'Dégâts aux champions par minute', m.damage_per_min, refs['damage'], unit='/min')
    m.vision_score = add('vision', 'Vision par minute', m.vision_per_min, refs['vision'], unit='/min')
    pink_ref = {'TOP':2, 'JUNGLE':4, 'MID':4, 'ADC':1, 'SUPPORT':4}.get(m.role, 2)*t/30
    m.pink_score = add('pinks', 'Balises de contrôle achetées', m.pinks, pink_ref,
                       observation=f'{m.pinks} achats en {fmt(t)} minutes. Ce critère ne mesure pas leur efficacité et garde un faible poids.')

    # Separate ally opportunities by kind; no Baron penalty simply because a
    # dragon was observed. Recorded assists cannot establish zoning participation.
    role_targets = {'TOP':(.35,.45), 'JUNGLE':(.75,.35), 'MID':(.5,.45),
                    'ADC':(.55,.5), 'SUPPORT':(.7,.5)}
    for idx, kind in enumerate(('epic', 'tower')):
        total = m.objective_opportunities.get(kind, 0)
        taken = m.objective_presence.get(kind, 0)
        target = role_targets.get(m.role, (.5,.45))[idx]
        add(kind, 'Participation aux monstres épiques' if kind == 'epic' else 'Participation aux tours',
            100*taken/total if total else 0, 100*target, unit=' %',
            observation=f'Présence enregistrée sur {taken:g} prise(s) alliée(s) sur {total:g}. Dernier coup et assistance ont la même valeur.',
            missing=not m.timeline_available or total == 0)
        parts[kind]['reference'] += ' Seules les participations enregistrées sont mesurées ; protéger les accès ou détourner les ennemis peut ne pas être crédité.'

    # Equal lane is neutral. Supports are not asked to take more CS than rivals.
    for key, label, value, available, spread in (
        ('gold15', 'Avance en or à 15 minutes', m.gold_diff_15, m.gold_15_available, 1500 if m.role != 'SUPPORT' else 750),
        ('cs15', 'Avance en sbires à 15 minutes', m.cs_diff_15, m.cs_15_available and m.role != 'SUPPORT', 30),
    ):
        unit = 'or' if key == 'gold15' else 'sbires et monstres'
        add(key, label, value, spread, missing=not available,
            observation=f'{"+" if value >= 0 else "−"}{fmt(abs(value),0)} {unit} par rapport à ton adversaire de rôle à 15 minutes.')
        if available:
            parts[key]['reference'] = f'Égalité : 5/10 ; +{spread} {unit} : 8/10 ; +{2*spread} : 10/10. Les retards équivalents valent 2 et 0/10. Cette mesure reste prise à 15 min, quelle que soit la durée finale.'
    m.gold_15_score, m.cs_15_score = parts['gold15']['score'], parts['cs15']['score']

    if utility_kind(m):
        text = []
        for p in m.utility_parts:
            if p['value'] is None:
                text.append(f"{p['label']} : donnée absente, exclue.")
            else:
                text.append(f"{p['label']} : {fmt(p['value']/t,2)}/min ; {rate_reference('utility',p['reference'],'/min')} Note {fmt(p['score'],2)}/10 ; poids {100*p['weight']:.0f} %.")
        parts['utility'] = dict(label='Aide apportée aux alliés',score=m.utility_score, neutral=not m.utility_available,
            observation=' '.join(text), reference='Seules les capacités adaptées au kit/profil sont attendues. Les références évoluent avec la durée. Un zéro connu sur une capacité attendue reste observé.')
    return parts, refs


def contribution_score(m):
    from .scoring import DIMENSION_WEIGHTS
    parts, refs = build_parts(m)
    t = m.game_minutes

    economy = [('dpg',.5),('cs',.25),('gold',.25)] if m.role != 'SUPPORT' else [('dpg',.5),('gold',.5)]
    if utility_kind(m) == 'primary':
        economy = [('gold',1)] if m.role == 'SUPPORT' else [('cs',.5),('gold',.5)]
    objectives = [('epic',.4),('tower',.4),('vision',.18),('pinks',.02)]
    if m.role in ('JUNGLE','SUPPORT'):
        objectives = [('epic',.45),('tower',.15),('vision',.35),('pinks',.05)]
    impact = [('damage',.6),('kp',.4)]
    if utility_kind(m) == 'primary':
        impact = [('utility',.8),('kp',.2)]
    elif utility_kind(m) == 'hybrid':
        impact = [('utility',.5),('damage',.3),('kp',.2)]
    definitions = (
        ('combat_value','⚔️ Combat',[('kda',.35),('kp',.35),('deaths',.3)]),
        ('economic_efficiency','💰 Économie',economy),
        ('objective_contribution','🎯 Objectifs',objectives),
        ('pace_rating','⚡ Tempo',[('gold15',1)] if m.role == 'SUPPORT' else [('gold15',.7),('cs15',.3)]),
        ('win_impact',"👑 Impact · apport à l’équipe",impact),
    )
    dimensions = []
    for key,title,weights in definitions:
        active = sum(w for name,w in weights if not parts[name]['neutral'])
        components = []
        for name,w in weights:
            part = dict(parts[name])
            part['weight'] = w/active if active and not part['neutral'] else 0.
            part['points'] = part['score']*part['weight']
            components.append(part)
        if not active:
            components.append(dict(label='Note neutre',score=5.,weight=1.,points=5.,neutral=True,
                                   observation='Aucun critère exploitable pour cette dimension.',reference='5/10 en attendant des observations suffisantes.'))
        score = sum(c['points'] for c in components)
        if key == 'pace_rating':
            bonus = ((.25 if m.has_first_blood or m.has_first_blood_assist else 0.) +
                     (.25 if m.has_first_tower or m.has_first_tower_assist else 0.) +
                     (min(.3,.1*m.early_solo_kills) if m.role in ('TOP','MID') else 0.)) if m.timeline_available else 0.
            bonus = min(bonus, 10-score)
            components.append(dict(label='Actions marquantes',score=0.,weight=0.,points=bonus,bonus=True,neutral=False,
                observation=f'Premier sang : {"oui" if m.has_first_blood or m.has_first_blood_assist else "non"}. Première tour : {"oui" if m.has_first_tower or m.has_first_tower_assist else "non"}. Éliminations en solo avant 15 min : {m.early_solo_kills}.'
                            + (f' Le bonus solo ne s’applique pas au rôle {m.role}.' if m.role not in ('TOP','MID') else ''),
                reference='Bonus uniquement : +0,25 par première action (assistance comprise), +0,10 par solo kill top/mid, limité à +0,30. Aucune pénalité sans ces événements.' if m.timeline_available else 'Historique des événements indisponible : aucun bonus inventé.'))
            score += bonus
        setattr(m,key,score)
        summary = dimension_summary(components)
        dimensions.append(dict(key=key,title=title,score=score,summary=summary,components=components))

    weights = DIMENSION_WEIGHTS[m.role_enum]
    names = ('combat','economic','objective','tempo','impact')
    adjusted = [max(0, w+getattr(m,name+'_weight_adj')) for (key,w),name in zip(weights.items(),names)]
    if not sum(adjusted):
        adjusted = list(weights.values())
    m.breakdown_score = 0.
    for (key,_),name,w in zip(weights.items(),names,adjusted):
        weight = w/sum(adjusted)
        setattr(m,'final_'+name+'_weight',weight)
        m.breakdown_score += getattr(m,key)*weight
    m.breakdown_score = max(0.,min(10.,m.breakdown_score))
    # Legacy SQL fields retained for compatibility; removed criteria are neutral.
    m.efficiency_score = m.tank_efficiency_score = 5.
    m.dragon_score = m.baron_score = m.turrets_killed_score = 5.
    m.turret_score = m.obj_damage_score = m.early_pressure_score = m.advantage_score = 5.
    m.obj_participation_score = parts['epic']['score']
    m.tower_participation_score = parts['tower']['score']
    m.fb_score = m.ft_score = m.solo_kills_score = 5.
    m.contribution_to_lead = 5.
    if not m.scoring_supported:
        m.breakdown_score = 5.
        for d in dimensions:
            setattr(m, d['key'], 5.)
            d.update(score=5.,summary='Mode ou rôle sans références adaptées : aucune évaluation.',components=[
                dict(label='Non évalué',score=5.,weight=1.,points=5.,neutral=True,
                     observation='Ce mode ou ce rôle inconnu ne dispose pas de barèmes adaptés.',
                     reference='Valeur neutre de compatibilité ; elle ne juge pas la performance.')])
    m.explanation_context = dict(version=2,scoring_version='5.0',role=m.role,profile=m.profile,
        duration_minutes=t,references=refs,dimensions=dimensions,
        statistical_components=getattr(m,'statistical_components',[]),
        dimension_weights={key:getattr(m,'final_'+name+'_weight') for key,name in zip(weights,names)})
