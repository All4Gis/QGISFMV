from math import degrees, radians, sin, cos, asin, atan2
from QGIS_FMV.QgsFmvConstants import EARTH_MEAN_RADIUS


def destination(point, distance, bearing):
    """
    Given a start point, initial bearing, and distance, this will
    calculate the destina­tion point and final bearing travelling
    along a (shortest distance) great circle arc.

    (see http://www.movable-type.co.uk/scripts/latlong.htm)
    """

    lon1, lat1 = (radians(coord) for coord in point)
    radians_bearing = radians(bearing)

    delta = distance / EARTH_MEAN_RADIUS

    lat2 = asin(sin(lat1) * cos(delta) + cos(lat1) * sin(delta) * cos(radians_bearing))
    numerator = sin(radians_bearing) * sin(delta) * cos(lat1)
    denominator = cos(delta) - sin(lat1) * sin(lat2)

    lon2 = lon1 + atan2(numerator, denominator)

    lon2_deg = (degrees(lon2) + 540) % 360 - 180
    lat2_deg = degrees(lat2)

    return (lon2_deg, lat2_deg)
