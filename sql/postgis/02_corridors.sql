-- Build corridors: maximal contiguous runs of same-street, same-borough,
-- same-treatment-history segments.
--
-- **Why ST_ClusterDBSCAN and not ST_LineMerge.** The obvious PostGIS idiom is
--
--     ST_Dump(ST_LineMerge(ST_Union(geom)))
--
-- and it was tried first. It produces a strictly finer partition than the
-- graph-based Python implementation: 67 corridors split, none merged. Two
-- causes, both real behaviours rather than bugs:
--
--   * ST_LineMerge sews linework only at *exactly* coincident endpoints. LION
--     centerlines are meant to share endpoints exactly, but coordinate
--     rounding leaves sub-foot gaps, and every one of those gaps becomes a
--     corridor break.
--   * ST_LineMerge stops at any node where three or more lines meet, because
--     it cannot decide which branch continues the run. Streets that fork and
--     rejoin therefore split, even though every piece is the same corridor.
--
-- ST_ClusterDBSCAN with eps = the endpoint tolerance expresses the definition
-- directly -- segments within tolerance of one another are one corridor,
-- transitively -- which is exactly what the Python connected-components build
-- computes. minpoints := 1 means no segment is discarded as noise; an isolated
-- segment is a one-segment corridor, not an outlier.

ALTER TABLE bike_segments ADD COLUMN IF NOT EXISTS geom geometry(Geometry, 2263);

UPDATE bike_segments
SET geom = ST_Transform(ST_GeomFromText(geom_wkt, 4326), 2263)
WHERE geom IS NULL;

CREATE INDEX IF NOT EXISTS bike_segments_geom_idx ON bike_segments USING GIST (geom);

DROP TABLE IF EXISTS segment_corridor CASCADE;

CREATE TABLE segment_corridor AS
WITH clustered AS (
    SELECT
        segmentid,
        street,
        boro_code,
        first_protected_year,
        geom,
        ST_ClusterDBSCAN(geom, eps := 10.0, minpoints := 1)
            OVER (PARTITION BY street, boro_code, first_protected_year) AS cluster_seq
    FROM bike_segments
)
SELECT
    segmentid,
    street,
    boro_code,
    first_protected_year,
    dense_rank() OVER (
        ORDER BY street, boro_code, first_protected_year, cluster_seq
    ) AS corridor_pk
FROM clustered;

DROP TABLE IF EXISTS corridors CASCADE;

CREATE TABLE corridors AS
SELECT
    sc.corridor_pk,
    any_value(sc.street)               AS street,
    any_value(sc.boro_code)            AS boro_code,
    any_value(sc.first_protected_year) AS first_protected_year,
    count(*)                           AS n_segments,
    ST_Union(bs.geom)                  AS geom,
    SUM(ST_Length(bs.geom))            AS length_ft
FROM segment_corridor sc
JOIN bike_segments bs USING (segmentid)
GROUP BY sc.corridor_pk;

CREATE INDEX corridors_geom_idx ON corridors USING GIST (geom);

-- Every segment must land in exactly one corridor. DBSCAN with minpoints := 1
-- guarantees this, so a violation means the partition key is wrong.
DO $$
DECLARE dupes integer;
BEGIN
    SELECT count(*) INTO dupes FROM (
        SELECT segmentid FROM segment_corridor
        GROUP BY segmentid HAVING count(DISTINCT corridor_pk) > 1
    ) x;
    IF dupes > 0 THEN
        RAISE EXCEPTION '% segments assigned to multiple corridors', dupes;
    END IF;
END $$;
