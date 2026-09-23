from geo.distance import haversine


def test_same_point_is_zero():
    assert haversine((0, 0), (0, 0)) == 0
