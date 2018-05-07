from collections import namedtuple
from math import pi


# https://en.wikipedia.org/wiki/Earth_radius#Mean_radius
EARTH_MEAN_RADIUS = 6371008.8
EARTH_MEAN_DIAMETER = 2 * EARTH_MEAN_RADIUS

# https://en.wikipedia.org/wiki/Earth_radius#Equatorial_radius
EARTH_EQUATORIAL_RADIUS = 6378137.0
EARTH_EQUATORIAL_METERS_PER_DEGREE = pi * \
    EARTH_EQUATORIAL_RADIUS / 180  # 111319.49079327358
I_EARTH_EQUATORIAL_METERS_PER_DEGREE = 1 / EARTH_EQUATORIAL_METERS_PER_DEGREE

HALF_PI = pi / 2.0
QUARTER_PI = pi / 4.0

# https://en.wikipedia.org/wiki/Geodetic_datum
Datum = namedtuple('Datum', ['a', 'b', 'e', 'f', 'w'])

# https://epsg.io/7030-ellipsoid
WGS84 = Datum(
    # equatorial radius (semi-major axis)
    a=6378137.0,
    # polar radius (semi-minor axis)
    b=6356752.314245179,  # b = a * (1 - f)
    # derived ellipsoid parameters
    # eccentricity
    e=0.08181919084262149,  # e = (2*f - f**2)**0.5
    # flattening
    f=0.0033528106647474805,  # 1/298.257223563
    # rotation speed
    w=7292115e-11,  # rad/sec;
)
