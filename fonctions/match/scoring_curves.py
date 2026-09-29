"""Explicit provisional score anchors, shared by calculation and explanations.

These are design references, not percentiles measured on Riot match history.
"""
import math


# Ratio to the role/profile/duration reference for scores 8 and 10.
RATE_TARGETS = {
    'kda': (2., 3.), 'cs': (1.25, 1.5), 'gold': (1.35, 1.65),
    'damage': (1.6, 2.2), 'dpg': (1.5, 2.), 'vision': (1.6, 2.4),
    'utility': (1.7, 2.5), 'cc': (1.7, 2.5), 'pinks': (1.5, 2.5),
}


def interpolate(value, anchors):
    if not math.isfinite(value):
        raise ValueError('Non-finite scoring observation')
    if value <= anchors[0][0]:
        return anchors[0][1]
    for (left, a), (right, b) in zip(anchors, anchors[1:]):
        if value <= right:
            return a + (b-a)*(value-left)/(right-left)
    return anchors[-1][1]


def rate_anchors(kind, reference):
    if not math.isfinite(reference) or reference <= 0:
        raise ValueError('Scoring reference must be finite and positive')
    good, excellent = RATE_TARGETS[kind]
    return ((0., 0.), (.5*reference, 2.), (reference, 5.),
            (good*reference, 8.), (excellent*reference, 10.))


def rate_score(kind, value, reference):
    return interpolate(value, rate_anchors(kind, reference))


def participation_score(value, reference, count, minimum):
    """Bounded 0..100%; finite small-sample caution, no permanent ceiling."""
    if not 0 < reference < 100 or not math.isfinite(count) or minimum <= 0:
        raise ValueError('Invalid participation reference or count')
    anchors = ((0., 0.), (reference, 5.), ((reference+100)/2, 8.), (100., 10.))
    raw = interpolate(value, anchors)
    confidence = min(1., max(0., count)/minimum)
    return 5 + confidence*(raw-5)


def survival_score(deaths, reference):
    # Zero deaths can reach ten; very high death counts approach zero gradually.
    if not math.isfinite(deaths) or not math.isfinite(reference) or reference <= 0:
        raise ValueError('Invalid survival observation or reference')
    ratio = max(0., deaths)/reference
    if ratio > 1.5:
        return 2/(1+(ratio-1.5))
    return interpolate(ratio, ((0., 10.), (.5, 8.), (1., 5.), (1.5, 2.)))


def advantage_score(value, good):
    if not math.isfinite(good) or good <= 0:
        raise ValueError('Invalid lane advantage reference')
    return interpolate(value, ((-2*good, 0.), (-good, 2.), (0., 5.),
                               (good, 8.), (2*good, 10.)))


def fmt(value, digits=1):
    return f'{value:,.{digits}f}'.replace(',', ' ').replace('.', ',')


def rate_reference(kind, reference, unit=''):
    _, _, neutral, good, excellent = rate_anchors(kind, reference)
    return (f'Repères du bot : {fmt(neutral[0])}{unit} → 5/10 ; '
            f'{fmt(good[0])}{unit} → 8/10 ; {fmt(excellent[0])}{unit} → 10/10. '
            'Entre ces repères, la note progresse régulièrement.')


def participation_reference(reference, count, minimum):
    text = (f'Repères : {fmt(reference)} % → 5/10 ; '
            f'{fmt((reference+100)/2)} % → 8/10 ; 100 % → 10/10.')
    if count < minimum:
        text += (f' Seulement {fmt(count, 0)} action(s) observée(s) : '
                 f'{fmt(100*max(0,count)/minimum, 0)} % de cette évaluation est retenue, '
                 'le reste garde la note neutre de 5/10.')
    return text


def dimension_summary(components):
    observed = [p for p in components if p['weight'] > 0 and not p['neutral']]
    if not observed:
        return 'Données insuffisantes : note neutre.'
    strong = max(observed, key=lambda p: (p['score']-5)*p['weight'])
    weak = min(observed, key=lambda p: (p['score']-5)*p['weight'])
    text = (f"Point fort : {strong['label'].lower()} ({fmt(strong['score'])}/10). "
            if strong['score'] >= 7 else '')
    if weak['score'] < 5:
        return text + f"Sous le repère du bot : {weak['label'].lower()} ({fmt(weak['score'])}/10)."
    return text + 'Tous les critères évalués atteignent ou dépassent le repère du bot.'
