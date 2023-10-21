import random, config

EPSILON = 1e-308
DEFAULT_STAT = 0.0
DEFAULT_WEIGHT = 1.0
DEFAULT_THRESHOLD = 0.5

def _nonzero(a: float):
    return EPSILON if a < EPSILON else a

def roll(stat=DEFAULT_STAT, weight=DEFAULT_WEIGHT):
    x = stat * weight
    if x < 0:
        x = -x
        return 1 - (1 / (1 / _nonzero(random.random()) + x) * (1 + x))
    else:
        return 1 / (1 / _nonzero(random.random()) + x) * (1 + x)

def roll_chance(stat=DEFAULT_STAT, weight=DEFAULT_WEIGHT, threshold=DEFAULT_THRESHOLD):
    return roll(stat, weight) < threshold

def get_weight(name):
    try:
        weight = config.config["roll_weights"][name]
        return weight
    except KeyError:
        return DEFAULT_WEIGHT

def get_threshold(name):
    try:
        threshold = config.config["roll_thresholds"][name]
        return threshold
    except KeyError:
        return DEFAULT_THRESHOLD