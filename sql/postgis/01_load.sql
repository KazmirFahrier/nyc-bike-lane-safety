-- Schema for the PostGIS corridor build.
--
-- This is a parallel implementation of nycbike.corridors, not a replacement.
-- DuckDB spatial builds the corridors the pipeline actually uses; this script
-- builds them independently in PostGIS and the two are compared segment for
-- segment. Two implementations that agree are evidence the corridor definition
-- is well specified rather than an artefact of one library's tolerances.

DROP TABLE IF EXISTS bike_segments CASCADE;

CREATE TABLE bike_segments (
    segmentid            text PRIMARY KEY,
    street               text,
    boro_code            text,
    first_protected_year integer,
    geom_wkt             text
);

-- Loaded by \copy from the exporter, then projected once into the city's own
-- planar CRS. Every distance below is therefore in US survey feet.
