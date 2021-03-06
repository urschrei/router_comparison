from __future__ import division
import requests
import json
import pandas as pd
import numpy as np
from itertools import chain
from shapely.geometry import LineString, Point


"""
If you wish to retrieve route data directly into a DataFrame

df['travel_time_valhalla'], df['valhalla_route'] = zip(*
    df.apply(route_valhalla, args=(origin_tuple), axis=1))

"""

def query_route_valhalla(
    key,
    start,
    end,
    costing,
    language="en_US",
    out_format="json",
    direction_params=None,
    costing_params=None):
    """
    Query a Valhalla instance for a route
    Returns travel time and list of route geometries
    
    key: Valhalla API key
    start: route start coords as a lon, lat iterable
    end: route end coords as a lon, lat iterable

    Not all options have been implemented here.
    See: https://github.com/valhalla/valhalla-docs/blob/gh-pages/api-reference.md#inputs-of-a-valhalla-route
    """
    allowed = ('pedestrian', 'bicycle', 'bus', 'auto', 'auto_shorter')
    if costing not in allowed:
        raise Exception(
            "Unknown travel method. Must be one of %s. Christ." % ', '.join(allowed))
    
    # build routing JSON
    initial_route = {
        "locations": [{"lat":start[1] ,"lon": start[0]}, {"lat":end[1] ,"lon":end[0]}],
        "costing": costing,
        "language": language,
        "out_format": out_format
    }
    route = initial_route.copy()
    if direction_params:
        route.update({'directions_options': direction_params})
    if costing_params:
        route.update({'costing_options': costing_params})
    endpoint = "https://valhalla.mapzen.com/route"
    params = {"json": json.dumps(route), "api_key": key}
    req = requests.get(endpoint, params=params)
    try:
        req.raise_for_status()
    except requests.exceptions.HTTPError:
        return (np.nan, np.nan)
    if req.json()['trip']['status'] == 207:
        return (np.nan, np.nan)
    return req.json()['trip']['summary']['time'], [leg['shape'] for leg in req.json()['trip']['legs']][0]


def query_route_osrm(start, end, method):
    """
    Get a route back from MapZen's OSRM
    start, end: lon, lat tuples
    method: foot, car, bicycle
    returns encoded Polyline
    TODO: bounds checking for coords
    """
    allowed = ('foot', 'car', 'bicycle')
    if method not in allowed:
        raise Exception(
            "Unknown method. Must be one of %s. Christ." % ', '.join(allowed))
    endpoint = 'http://osrm.mapzen.com'
    method = '/{m}/viaroute'.format(m=method)
    # should be properly encoding second loc, but dict keys are unique!
    # reverse lon, lat because ugh    
    params = {'loc': '{1},{0}&loc={3},{2}'.format(*chain(start, end))}
    req = requests.get(endpoint + method, params=params)
    try:
        req.raise_for_status()
    except requests.exceptions.HTTPError:
        return (np.nan, np.nan)
    if req.json().get('status') == 207:
        return np.nan, np.nan
    return req.json()['route_summary']['total_time'], req.json()['route_geometry']


def query_route_gmaps(start, end, method, key):
    """ retrieve a bike route from GMaps """
    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": "%s, %s" % (start[1], start[0]),
        "destination": "%s, %s" % (end[1], end[0]),
        "mode": method,
        "units": "metric",
        "region": "uk",
        "key": key

    }
    req = requests.get(url, params=params)
    try:
        req.raise_for_status()
    except requests.exceptions.HTTPError:
        return (np.nan, np.nan)
    # currently one route, containing one leg
    try:
        route = req.json()['routes'][0]
        leg = req.json()['routes'][0]['legs'][0]
        duration = sum([step['duration']['value'] for step in leg['steps']])
        overview_polyline = route['overview_polyline']['points']
    except (KeyError, IndexError):
        return (np.nan, np.nan)
    return duration, overview_polyline


def query_elevation(polyline, key):
    """ retrieve elevations for a polyline from GMaps """
    url = "https://maps.googleapis.com/maps/api/elevation/json"
    params = {
        "locations": "enc:%s" % polyline,
        "key": key
    }
    req = requests.get(url, params=params)
    try:
        req.raise_for_status()
    except requests.exceptions.HTTPError:
        return np.nan
    try:
        elevations = req.json()['results']
    except (KeyError, IndexError):
        return np.nan
    return elevations


def route_valhalla(df, start):
    return query_route_valhalla(api_key, start, (df['lon'], df['lat']), 'bicycle')


def route_gmaps(df, start):
    return query_route_gmaps(start, (df['lon'], df['lat']), 'bicycling', gmaps_key)


def route_osrm(df, start):
    return query_route_osrm(start, (df['lon'], df['lat']), 'bicycle')


def decode_polyline(point_str, gmaps=False):
    """
    Decodes a polyline that has been encoded using Google's algorithm
    http://code.google.com/apis/maps/documentation/polylinealgorithm.html
    
    This is a generic method that returns a list of (lon, lat) 
    tuples, which are used as input to a Shapely LineString
    
    point_str: encoded polyline string
    returns: LineString instance
    """
    # some coordinate offsets are represented by 4 to 5 binary chunks
    if pd.isnull(point_str):
        return np.nan
    coord_chunks = [[]]
    for char in point_str:
        # convert each character to decimal from ascii
        value = ord(char) - 63
        # values that have a chunk following have an extra 1 on the left
        split_after = not (value & 0x20)   
        value &= 0x1F
        coord_chunks[-1].append(value)
        if split_after:
            coord_chunks.append([])
    del coord_chunks[-1]
    coords = []
    for coord_chunk in coord_chunks:
        coord = 0
        for i, chunk in enumerate(coord_chunk):
            coord |= chunk << (i * 5)
        # there is a 1 on the right if the coord is negative
        if coord & 0x1:
            coord = ~coord #invert
        coord >>= 1
        # https://github.com/Project-OSRM/osrm-backend/issues/713
        # (OSRM returns higher-precision coordinates)
        # NB this is not the case for Google Directions Polylines
        # they only need coord /= 100000.
        if not gmaps:
            coord /= 1000000.
        else:
            coord /= 100000.
        coords.append(coord)
    # convert the 1d list to a 2d list & offsets to actual values
    points = []
    prev_x = 0
    prev_y = 0
    for i in xrange(0, len(coords) - 1, 2):
        if coords[i] == 0 and coords[i + 1] == 0:
            continue
        prev_x += coords[i + 1]
        prev_y += coords[i]
        # rounding to 6 digits ensures that the floats are the same as when 
        # they were encoded
        points.append((round(prev_x, 6), round(prev_y, 6)))
    if len(points) > 1:
        return LineString(points)
    else:
        return np.nan


def project_linestring(ls, m, inverse=False):
    """ return a linestring projected into map coordinates """
    if not pd.isnull(ls):
        return LineString(zip(*m(*zip(*ls.coords))))
    else:
        return np.nan


def similarity(ls1, ls2):
    """
    Calculate LineString similarity percentage
    & is untion, | is intersection

    """
    set1 = set(ls1.coords)
    set2 = set(ls2.coords)
    return (len(set1 & set2) / len(set1 | set2)) * 100


def pairs(line):
    """ yield line segment start and end points for input line """
    for i in xrange(1, len(line)):
        yield line[i - 1], line[i]


def segmentise(line):
    """ returns a list of linestring sub-segments for the input """
    return [
        LineString([Point(seg_start).coords[0], Point(seg_end).coords[0]])
        for seg_start, seg_end in pairs(line.coords)
    ]
