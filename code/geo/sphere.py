# -*- coding: utf-8 -*-
from math import (
    degrees, radians,
    sin, cos, asin, tan, atan, atan2, pi,
    sqrt, exp, log, fabs
)

from QGIS_FMV.geo.constants import (
    EARTH_MEAN_RADIUS,
    EARTH_MEAN_DIAMETER,
    EARTH_EQUATORIAL_RADIUS,
    EARTH_EQUATORIAL_METERS_PER_DEGREE,
    I_EARTH_EQUATORIAL_METERS_PER_DEGREE,
    HALF_PI,
    QUARTER_PI,
)


def _py_approximate_distance(point1, point2):
    '''
        Approximate calculation distance
        (expanding the trigonometric functions around the midpoint)
    '''

    lon1, lat1 = (radians(coord) for coord in point1)
    lon2, lat2 = (radians(coord) for coord in point2)
    cos_lat = cos((lat1 + lat2) / 2.0)
    dx = (lat2 - lat1)
    dy = (cos_lat * (lon2 - lon1))
    return EARTH_MEAN_RADIUS * sqrt(dx ** 2 + dy ** 2)


def _py_haversine_distance(point1, point2):
    '''
        Calculating haversine distance between two points
        (see https://en.wikipedia.org/wiki/Haversine_formula,
            https://www.math.ksu.edu/~dbski/writings/haversine.pdf)

        Is numerically better-conditioned for small distances
    '''
    lon1, lat1 = (radians(coord) for coord in point1[:2])
    lon2, lat2 = (radians(coord) for coord in point2[:2])
    dlat = (lat2 - lat1)
    dlon = (lon2 - lon1)
    a = (
        sin(dlat * 0.5) ** 2 +
        cos(lat1) * cos(lat2) * sin(dlon * 0.5) ** 2
    )

    return EARTH_MEAN_DIAMETER * asin(sqrt(a))


def _py_distance(point1, point2):
    '''
        Calculating great-circle distance
        (see https://en.wikipedia.org/wiki/Great-circle_distance)
    '''
    lon1, lat1 = (radians(coord) for coord in point1)
    lon2, lat2 = (radians(coord) for coord in point2)

    dlon = fabs(lon1 - lon2)
    dlat = fabs(lat1 - lat2)

    numerator = sqrt(
        (cos(lat2) * sin(dlon)) ** 2 +
        ((cos(lat1) * sin(lat2)) - (sin(lat1) * cos(lat2) * cos(dlon))) ** 2)

    denominator = (
        (sin(lat1) * sin(lat2)) +
        (cos(lat1) * cos(lat2) * cos(dlon)))

    c = atan2(numerator, denominator)
    return EARTH_MEAN_RADIUS * c


def bearing(point1, point2):
    '''
        Calculating initial bearing between two points
        (see http://www.movable-type.co.uk/scripts/latlong.html)
    '''
    lon1, lat1 = (radians(coord) for coord in point1)
    lon2, lat2 = (radians(coord) for coord in point2)

    dlat = (lat2 - lat1)
    dlon = (lon2 - lon1)
    numerator = sin(dlon) * cos(lat2)
    denominator = (
        cos(lat1) * sin(lat2) -
        (sin(lat1) * cos(lat2) * cos(dlon))
    )

    theta = atan2(numerator, denominator)
    theta_deg = (degrees(theta) + 360) % 360
    return theta_deg


def final_bearing(point1, point2):
    return (bearing(point2, point1) + 180) % 360


def destination(point, distance, bearing):
    '''
        Given a start point, initial bearing, and distance, this will
        calculate the destina­tion point and final bearing travelling
        along a (shortest distance) great circle arc.

        (see http://www.movable-type.co.uk/scripts/latlong.htm)
    '''

    lon1, lat1 = (radians(coord) for coord in point)
    radians_bearing = radians(bearing)

    delta = distance / EARTH_MEAN_RADIUS

    lat2 = asin(
        sin(lat1) * cos(delta) +
        cos(lat1) * sin(delta) * cos(radians_bearing)
    )
    numerator = sin(radians_bearing) * sin(delta) * cos(lat1)
    denominator = cos(delta) - sin(lat1) * sin(lat2)

    lon2 = lon1 + atan2(numerator, denominator)

    lon2_deg = (degrees(lon2) + 540) % 360 - 180
    lat2_deg = degrees(lat2)

    return (lon2_deg, lat2_deg)


def approximate_destination(point, distance, theta):
    # http://stackoverflow.com/questions/2187657/calculate-second-point-knowing-the-starting-point-and-distance
    lon, lat = point
    radians_theta = radians(theta)
    dx = distance * cos(radians_theta)
    dy = distance * sin(radians_theta)

    dlon = dx / (EARTH_EQUATORIAL_METERS_PER_DEGREE * cos(radians(lat)))
    dlat = dy / EARTH_EQUATORIAL_METERS_PER_DEGREE

    return (lon + dlon, lat + dlat)


def _py_from4326_to3857(point):
    '''
        Reproject point from EPSG:4326 to EPSG:3857
        (see
            http://wiki.openstreetmap.org/wiki/Mercator,
            https://epsg.io/4326,
            https://epsg.io/3857)
    '''
    lon, lat = point
    xtile = lon * EARTH_EQUATORIAL_METERS_PER_DEGREE
    ytile = log(tan(radians(45 + lat / 2.0))) * EARTH_EQUATORIAL_RADIUS
    return (xtile, ytile)


def _py_from3857_to4326(point):
    '''
        Reproject point from EPSG:3857 to EPSG:4326
        (see http://wiki.openstreetmap.org/wiki/Mercator)

        Reverse Spherical Mercator:
            λ = E/R + λo
            φ = π/2 - 2*arctan(exp(-N/R))
    '''
    x, y = point
    lon = x / EARTH_EQUATORIAL_METERS_PER_DEGREE
    lat = degrees(2.0 * atan(exp(y / EARTH_EQUATORIAL_RADIUS)) - HALF_PI)
    return (lon, lat)


try:
    from ._sphere import (
        _approximate_distance,
        _haversine_distance,
        _distance,
        _from4326_to3857,
        _from3857_to4326,
    )
    approximate_distance = _approximate_distance
    haversine_distance = _haversine_distance
    distance = _distance
    from4326_to3857 = _from4326_to3857
    from3857_to4326 = _from3857_to4326
except ImportError:  # pragma: no cover
    approximate_distance = _py_approximate_distance
    haversine_distance = _py_haversine_distance
    distance = _py_distance
    from4326_to3857 = _py_from4326_to3857
    from3857_to4326 = _py_from3857_to4326
