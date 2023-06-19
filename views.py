import logging
import time
import aiohttp
import aiohttp_jinja2
import itertools
from aiohttp import web
from aiohttp_session import get_session
import collections
import statistics

import numpy as np
from scipy.spatial import Voronoi, voronoi_plot_2d
import shapely.geometry
import shapely.ops


log          = logging.getLogger(__name__)
nWsCounter   = 0
dictTableMap = dict()
dictUserToHighscore = dict()
nPolygonBufferSize = 0.1
nRandomPointCount = 1500
nMaxPointX = 1
nMaxPointY = 1
nMinPointX = 0
nMinPointY = 0

dictIndexToColor = {"0" : 'red',
                    "1" : 'yellow',
                    "2" : 'blue'}

def FixZeroCoordinates(listPoint):
    FixZero = lambda coord: 0 if coord < 0 else coord
    FixMoreVal = lambda coord, Val: 1 if coord > Val else coord
    listPoint[0] = FixMoreVal(FixZero(listPoint[0]), nMaxPointX)
    listPoint[1] = FixMoreVal(FixZero(listPoint[1]), nMaxPointY)
    return listPoint


def GetSvgStringFromPolygon(shpPolygon, listResultStrings):
    sSvgCoordinates = ''
    listPolygonCoordinates = list(shpPolygon.exterior.coords)

    for i  in listPolygonCoordinates:
        X = round((i[0] - nPolygonBufferSize) * 700)
        Y = round((i[1] - nPolygonBufferSize) * 700)
        if X < 0 or Y < 0:
            sSvgCoordinates = ''
            break
        sSvgCoordinates += '%s,%s ' % (X, Y)

    sSvgCoordinates = sSvgCoordinates.strip()

    if sSvgCoordinates:
        listResultStrings.append(sSvgCoordinates)
    else:
        listResultStrings.append('')


def GetNeighborsPolygon(dictIndexToPolygon):

    dictPolygonIndexToSetOfNeighbors = collections.defaultdict(set)
    setChecked = set()

    for nIndex1, nIndex2 in itertools.permutations(dictIndexToPolygon, r = 2):
        if (nIndex1, nIndex2) not in setChecked or (nIndex2, nIndex1) not in setChecked:
            if dictIndexToPolygon[nIndex1].touches(dictIndexToPolygon[nIndex2]):
                dictPolygonIndexToSetOfNeighbors[nIndex1].add(nIndex2)
                dictPolygonIndexToSetOfNeighbors[nIndex2].add(nIndex1)
                setChecked.add((nIndex1, nIndex2))
                setChecked.add((nIndex2, nIndex1))

    return dictPolygonIndexToSetOfNeighbors


def UnionSmallPolygons(listResultPolygons, dictPolygonIndexToSetOfNeighbors, nMinArea):
    setPolygonsForRemove = set()
    setUnionPolygons     = set()
    for nPolygonIndex, shpPolygon in enumerate(listResultPolygons):
        if shpPolygon.area < nMinArea and nPolygonIndex not in setUnionPolygons:
            setNeighbourPolygons = dictPolygonIndexToSetOfNeighbors[nPolygonIndex]
            setNeighbourPolygons = setNeighbourPolygons.difference(setUnionPolygons)
            setNeighbourPolygons = setNeighbourPolygons.difference(setPolygonsForRemove)

            if not setNeighbourPolygons:
                continue

            listNeighbourPolygonsArea = list()
            for nNeighbourPolygonIndex in setNeighbourPolygons:
                objNeighbourPolygon = listResultPolygons[nNeighbourPolygonIndex]
                listNeighbourPolygonsArea.append([objNeighbourPolygon.area, nNeighbourPolygonIndex])

            listNeighbourPolygonsArea.sort()
            nIndexPolyForUnion = statistics.median_low(range(0, len(listNeighbourPolygonsArea)))
            nIndexPolyForUnion = listNeighbourPolygonsArea[nIndexPolyForUnion][1]
            listResultPolygons[nIndexPolyForUnion] = listResultPolygons[nIndexPolyForUnion].union(shpPolygon)
            setNeighbourPolygons.remove(nIndexPolyForUnion)
            dictPolygonIndexToSetOfNeighbors[nIndexPolyForUnion].update(setNeighbourPolygons)
            dictPolygonIndexToSetOfNeighbors[nIndexPolyForUnion].remove(nPolygonIndex)
            listResultPolygons[nPolygonIndex] = listResultPolygons[nIndexPolyForUnion]
            dictPolygonIndexToSetOfNeighbors[nPolygonIndex] = dictPolygonIndexToSetOfNeighbors[nIndexPolyForUnion]
            setPolygonsForRemove.add(nPolygonIndex)
            setUnionPolygons.add(nIndexPolyForUnion)

    listResultPolygons = [shpPolygon for nPolyIndex, shpPolygon in enumerate(listResultPolygons) if nPolyIndex not in setPolygonsForRemove]
    return listResultPolygons, len(setPolygonsForRemove)


def GetVoronoiPolygons(nRandomPointCount):

    #points = np.random.random((nRandomPointCount, 2))
    pointsX = np.random.uniform(0, nMaxPointX, nRandomPointCount)
    pointsY = np.random.uniform(0, nMaxPointY, nRandomPointCount)
    points = np.column_stack((pointsX, pointsY))
    vor = Voronoi(points)

    lines = list()
    for line in vor.ridge_vertices:
        listVorLine = vor.vertices[line]
        listVorLine = list(map(FixZeroCoordinates, listVorLine))
        lines.append(shapely.geometry.LineString(listVorLine))

    # Create bounding box for cut set of polygons
    mlsWithoutBbox = shapely.geometry.MultiLineString(lines)
    min_x, min_y, max_x, max_y =  mlsWithoutBbox.bounds
    min_x, min_y, max_x, max_y = min_x + nPolygonBufferSize, min_y + nPolygonBufferSize, max_x - nPolygonBufferSize, max_y - nPolygonBufferSize
    box = shapely.geometry.Polygon([[min_x, min_y], [min_x, max_y], [max_x, max_y], [max_x, min_y]])

    # Cut polygons by bounding box and resolve issues with GEOMETRYCOLLECTION
    listResultPolygons = list()
    listWithResultPolygons = shapely.ops.polygonize(mlsWithoutBbox)
    for shpPolygon in listWithResultPolygons:
        shpPolygon = shpPolygon.intersection(box)
        if shpPolygon.geom_type.upper() == 'GEOMETRYCOLLECTION':
            for shpGeom in shpPolygon:
                if shpGeom.geom_type.upper() == 'POLYGON':
                    listResultPolygons.append(shpGeom)

        elif shpPolygon.geom_type.upper() == 'POLYGON':
            listResultPolygons.append(shpPolygon)

    # Get neighbours for each polygon
    dictPolygonIndexToSetOfNeighbors = GetNeighborsPolygon(dict(zip(range(0, len(listResultPolygons)), listResultPolygons)))

    # Union small polygons and recalculate neighbours polygons
    nMinArea = statistics.median([shpPolygon.area for shpPolygon in listResultPolygons])

    nDissolvedPolygonCount = -1
    while nDissolvedPolygonCount != 0:
        listResultPolygons, nDissolvedPolygonCount = UnionSmallPolygons(listResultPolygons, dictPolygonIndexToSetOfNeighbors, nMinArea)
        dictPolygonIndexToSetOfNeighbors = GetNeighborsPolygon(dict(zip(range(0, len(listResultPolygons)), listResultPolygons)))

    # Prepare svg strings for html view
    listResultStrings  = list()
    for shpGeom in listResultPolygons:
        GetSvgStringFromPolygon(shpGeom, listResultStrings)

    return list(enumerate(listResultStrings)), dictPolygonIndexToSetOfNeighbors


def CheckNighboursColor(dictPolygonIndexToSetOfNeighbors, dictTableMap, sPolygonId, sColor):

    if sPolygonId in dictTableMap:
        return False

    setNeighbourPolygons = dictPolygonIndexToSetOfNeighbors[sPolygonId]
    for sNeighbourPolygonId in setNeighbourPolygons:
        if sNeighbourPolygonId in dictTableMap:
            sNeighbourColor = dictTableMap[sNeighbourPolygonId]['color']
            if sColor == sNeighbourColor:
                return False
    return True


VoronoiPolygons, dictPolygonIndexToSetOfNeighbors = GetVoronoiPolygons(nRandomPointCount)

async def index(request):

    global dictTableMap, VoronoiPolygons, dictPolygonIndexToSetOfNeighbors, dictUserToHighscore
##    sUser             = int(time.time())
    session = await get_session(request)

    sUser = session.get("user")
    if sUser not in dictUserToHighscore:
        dictUserToHighscore[sUser] = 0

    ws_current = web.WebSocketResponse()

    # If user run app at the first time
    ws_ready = ws_current.can_prepare(request)
    if not ws_ready.ok:
        return aiohttp_jinja2.render_template('index.html', request, {'Polygons' : VoronoiPolygons, 'sUser' : sUser})

    await ws_current.prepare(request)

    for sPolygonId in dictTableMap:
        await ws_current.send_json({'action': 'sent', 'text': dictTableMap[sPolygonId]})

    global nWsCounter
    nWsIndex = nWsCounter
    request.app['websockets'][nWsIndex] = ws_current
    nWsCounter += 1

    while True:

        try:
            msg = await ws_current.receive_json()
        except:
            print ('issue with ws_current.receive_json()')
            try:
                await ws_current.send_json({'action': 'disconnect', 'text': msg})
            except:
                break
            break

        if msg:

            sSvgId       = msg['SvgId']
            sPolygonId   = int(sSvgId[4:])
            sColorIndex  = msg['color']
            sColor       = dictIndexToColor[sColorIndex]
            msg['color']     = sColor
            msg['PolygonId'] = sPolygonId

            isAllowToPaint = CheckNighboursColor(dictPolygonIndexToSetOfNeighbors, dictTableMap, sPolygonId, sColor)

            if not isAllowToPaint:
                for ws in request.app['websockets'].values():
                    # If ws is not ws_current:
                    await ws.send_json({'action': 'forbidden', 'text': msg})
                continue

            dictTableMap[sPolygonId] = msg

            for ws in request.app['websockets'].values():

                # If ws is not ws_current:
                await ws.send_json({'action': 'sent', 'text': msg})

            dictUserToHighscore[sUser] += 1
            await ws_current.send_json({'action': 'highscore', 'text': dictUserToHighscore[sUser]})

        else:
            break

    await request.app['websockets'][nWsIndex].close()

    del request.app['websockets'][nWsIndex]

    return ws_current


async def restart(request):

    global dictTableMap, VoronoiPolygons, dictPolygonIndexToSetOfNeighbors

    try:

        for ws in request.app['websockets'].values():
            # If ws is not ws_current:
            await ws.send_json({'action': 'disconnect', 'text': {}})

        VoronoiPolygons, dictPolygonIndexToSetOfNeighbors = GetVoronoiPolygons(nRandomPointCount)
        dictTableMap = dict()

        return web.Response(text='Restarted!')

    except:
        return web.Response(text='Error with  restarted!')


