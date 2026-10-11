from geo.utils import normalize

PLACES = {}


def store_place(name, coords):
    PLACES[name] = normalize(coords)
