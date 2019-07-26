  # -*- coding: utf-8 -*-
from math import (
    degrees, radians,
    sin, cos, tan, atan, atan2,
    sqrt, exp, log
)

from QGIS_FMV.geo.constants import WGS84, QUARTER_PI, HALF_PI

CONVERGENCE_THRESHOLD = 1e-12
MAX_ITERATIONS = 15


def _py_distance(point1, point2, ellipsoid=WGS84):
    '''
        Calculating distance with using vincenty's formula
        https://en.wikipedia.org/wiki/Vincenty's_formulae
    '''
    lon1, lat1 = (radians(coord) for coord in point1)
    lon2, lat2 = (radians(coord) for coord in point2)

    U1 = atan((1 - ellipsoid.f) * tan(lat1))
    U2 = atan((1 - ellipsoid.f) * tan(lat2))
    L = lon2 - lon1
    Lambda = L

    sinU1 = sin(U1)
    cosU1 = cos(U1)
    sinU2 = sin(U2)
    cosU2 = cos(U2)

    for _ in range(MAX_ITERATIONS):
        sinLambda = sin(Lambda)
        cosLambda = cos(Lambda)
        sinSigma = sqrt(
            (cosU2 * sinLambda) ** 2 + 
            (cosU1 * sinU2 - sinU1 * cosU2 * cosLambda) ** 2)
        # coincident points
        if sinSigma == 0:
            return 0.0

        cosSigma = sinU1 * sinU2 + cosU1 * cosU2 * cosLambda
        sigma = atan2(sinSigma, cosSigma)
        sinAlpha = cosU1 * cosU2 * sinLambda / sinSigma
        cosSqAlpha = 1 - sinAlpha ** 2
        try:
            cos2SigmaM = cosSigma - 2 * sinU1 * sinU2 / cosSqAlpha
        except ZeroDivisionError:
            cos2SigmaM = 0

        C = (ellipsoid.f / 16) * cosSqAlpha * (
            4 + ellipsoid.f * (4 - 3 * cosSqAlpha)
        )
        LambdaPrev = Lambda
        Lambda = (
            L + (1 - C) * ellipsoid.f * sinAlpha * (
                sigma + C * sinSigma * (
                    cos2SigmaM + C * cosSigma * (
                        -1 + 2 * cos2SigmaM ** 2
                    )
                )
            )
        )

        if abs(Lambda - LambdaPrev) < CONVERGENCE_THRESHOLD:
            break
    else:
        # failure to converge
        return None

    uSq = cosSqAlpha * (ellipsoid.a ** 2 - ellipsoid.b ** 
                        2) / (ellipsoid.b ** 2)
    A = 1 + uSq / 16384 * (4096 + uSq * (-768 + uSq * (320 - 175 * uSq)))
    B = uSq / 1024 * (256 + uSq * (-128 + uSq * (74 - 47 * uSq)))
    deltaSigma = B * sinSigma * (cos2SigmaM + B / 4 * (cosSigma * 
                                                       (-1 + 2 * cos2SigmaM ** 2)
                                                       -B / 6 * cos2SigmaM * 
                                                       (-3 + 4 * sinSigma ** 2)
                                                       * (-3 + 4 * cos2SigmaM
                                                          ** 2)))
    s = ellipsoid.b * A * (sigma - deltaSigma)
    return s


def _py_from4326_to3395(point, ellipsoid=WGS84):
    '''
        https://en.wikipedia.org/wiki/Mercator_projection#Generalization_to_the_ellipsoid
        http://epsg.io/3395

        Ellipsoidal Mercator:
            E = a*(λ - λo)
            N = a*ln(tan(π/4+φ/2)*((1-e*sin(φ))/(1+e*sin(φ)))**e/2)
    '''
    lon, lat = (radians(coord) for coord in point)
    e = ellipsoid.e
    a = ellipsoid.a
    e_sin_lat = e * sin(lat)
    multiplier1 = tan(QUARTER_PI + lat / 2.0)
    multiplier2 = pow((1 - e_sin_lat) / (1 + e_sin_lat), e / 2)
    E = a * lon
    N = a * log(multiplier1 * multiplier2)
    return (E, N)


def _py_from3395_to4326(point, ellipsoid=WGS84):
    '''
        Reverse Ellipsoidal Mercator:
            λ = E/a + λo
            φ = π/2 + 2*arctan(exp(-N/a)*((1-e*sin(φ))/(1+e*sin(φ))**e/2))
    '''
    E, N = point
    e = ellipsoid.e
    a = ellipsoid.a
    half_e = e * 0.5

    m1 = exp(-N / a)
    old_phi = HALF_PI - 2.0 * atan(m1)

    for _ in range(MAX_ITERATIONS):
        e_sin_phi = e * sin(old_phi)
        m2 = ((1 - e_sin_phi) / (1 + e_sin_phi)) ** half_e
        phi = HALF_PI - 2.0 * atan(m1 * m2)
        if abs(old_phi - phi) <= CONVERGENCE_THRESHOLD:
            break
        old_phi = phi

    lon = degrees(E / a)
    lat = degrees(phi)
    return (lon, lat)


distance = _py_distance
from4326_to3395 = _py_from4326_to3395
from3395_to4326 = _py_from3395_to4326
