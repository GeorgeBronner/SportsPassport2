import { geoAlbersUsa, geoPath } from 'd3-geo';
import { mesh, merge } from 'topojson-client';
import type { Topology, GeometryCollection, Polygon, MultiPolygon } from 'topojson-specification';
import usTopology from '../../data/us-states-10m.json';

// Real US Census state boundaries (via us-atlas, 10m resolution) through a
// proper Albers USA projection — the same projection/data family behind most
// "map of the US" renderings. Alaska and Hawaii are dropped (FIPS 02/15):
// this is a games-attended tracker with no non-continental venues, and
// their standard AlbersUSA insets ate space for little payoff here.
export const MAP_W = 946;
export const MAP_H = 520;

const NON_CONTINENTAL_FIPS = new Set(['02', '15']);

const topology = usTopology as unknown as Topology;
const allStates = topology.objects.states as GeometryCollection;
const continentalGeoms = allStates.geometries.filter(
  (g): g is Polygon | MultiPolygon => !NON_CONTINENTAL_FIPS.has(String(g.id))
);
const continentalStates: GeometryCollection = { type: 'GeometryCollection', geometries: continentalGeoms };
const nationGeo = merge(topology, continentalGeoms);

const PADDING = 14;
const projection = geoAlbersUsa().fitExtent(
  [[PADDING, PADDING], [MAP_W - PADDING, MAP_H - PADDING]],
  nationGeo
);
const path = geoPath(projection);

/** Project a (lat, lon) pair to SVG [x, y]; null if it falls outside the
 * projected area (e.g. Alaska, Hawaii, or an international venue) — callers
 * should simply not render that point. */
export const projectPoint = (lat: number, lon: number): [number, number] | null => {
  const p = projection([lon, lat]);
  return p ? [p[0], p[1]] : null;
};

/** Filled/outlined continental landmass (all states dissolved into one shape). */
export const US_PATH: string = path(nationGeo) ?? '';

/** Interior state boundary lines, drawn lighter than the coastline. */
export const STATE_BORDERS_PATH: string = path(mesh(topology, continentalStates, (a, b) => a !== b)) ?? '';
