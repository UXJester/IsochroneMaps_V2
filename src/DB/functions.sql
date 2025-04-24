-- IsochroneMapsV2 SQL Functions
-- This file contains SQL functions used by the application

-- Function to get locations within an isochrone
-- Returns all locations that are within a specified isochrone
CREATE OR REPLACE FUNCTION get_locations_within_isochrone(isochrone_id INTEGER)
RETURNS TABLE (
    id INTEGER,
    name TEXT,
    address TEXT,
    city TEXT,
    state VARCHAR(2),
    zip_code VARCHAR(10),
    latitude NUMERIC(9,6),
    longitude NUMERIC(9,6),
    category TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        l.id, l.name, l.address, l.city, l.state,
        l.zip_code, l.latitude, l.longitude, l.category
    FROM
        locations l, isochrones i
    WHERE
        i.id = isochrone_id
        AND ST_Contains(i.geometry, l.geom);
END;
$$ LANGUAGE plpgsql;

-- Function to get isochrones intersecting a given isochrone
-- Useful for finding where service areas overlap
CREATE OR REPLACE FUNCTION get_intersecting_isochrones(isochrone_id INTEGER)
RETURNS TABLE (
    id INTEGER,
    name TEXT,
    value INTEGER,
    intersection_area FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        i2.id, i2.name, i2.value,
        ST_Area(ST_Intersection(i1.geometry, i2.geometry)::geography)/1000000 AS intersection_area_km2
    FROM
        isochrones i1, isochrones i2
    WHERE
        i1.id = isochrone_id
        AND i1.id != i2.id
        AND ST_Intersects(i1.geometry, i2.geometry)
    ORDER BY
        intersection_area_km2 DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to create a user-generated isochrone
-- This function is called from the map interface when a user creates a custom isochrone
CREATE OR REPLACE FUNCTION create_user_isochrone(
    p_user_id UUID,
    p_name TEXT,
    p_value INTEGER,
    p_latitude NUMERIC(9,6),
    p_longitude NUMERIC(9,6),
    p_geometry TEXT -- GeoJSON geometry string
)
RETURNS INTEGER AS $$
DECLARE
    new_id INTEGER;
    center_point geometry;
    iso_geometry geometry;
BEGIN
    -- Create center point from coordinates
    center_point := ST_SetSRID(ST_MakePoint(p_longitude, p_latitude), 4326);

    -- Convert GeoJSON to PostGIS geometry
    iso_geometry := ST_SetSRID(ST_GeomFromGeoJSON(p_geometry), 4326);

    -- Insert the isochrone
    INSERT INTO user_isochrones (
        user_id,
        name,
        value,
        center,
        geometry,
        metadata
    ) VALUES (
        p_user_id,
        p_name,
        p_value,
        center_point,
        iso_geometry,
        jsonb_build_object(
            'created_by', 'map_interface',
            'latitude', p_latitude,
            'longitude', p_longitude
        )
    )
    RETURNING id INTO new_id;

    RETURN new_id;
END;
$$ LANGUAGE plpgsql;

-- Function to calculate the total area covered by isochrones for a specific center
CREATE OR REPLACE FUNCTION get_isochrone_area_stats(center_name TEXT)
RETURNS TABLE (
    iso_value INTEGER,
    area_km2 FLOAT,
    perimeter_km FLOAT,
    poi_count INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        i.value,
        ST_Area(i.geometry::geography)/1000000 AS area_km2,
        ST_Perimeter(i.geometry::geography)/1000 AS perimeter_km,
        COUNT(DISTINCT l.id) AS poi_count
    FROM
        isochrones i
    LEFT JOIN
        locations l ON ST_Contains(i.geometry, l.geom)
    WHERE
        i.name = center_name
    GROUP BY
        i.value, i.geometry
    ORDER BY
        i.value;
END;
$$ LANGUAGE plpgsql;

-- Function to find the nearest city center to a given coordinate
CREATE OR REPLACE FUNCTION find_nearest_center(
    p_latitude NUMERIC(9,6),
    p_longitude NUMERIC(9,6),
    p_limit INTEGER DEFAULT 5
)
RETURNS TABLE (
    id INTEGER,
    city TEXT,
    state VARCHAR(2),
    distance_km FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.city,
        c.state,
        ST_Distance(
            c.geom::geography,
            ST_SetSRID(ST_MakePoint(p_longitude, p_latitude), 4326)::geography
        )/1000 AS distance_km
    FROM
        city_centers c
    ORDER BY
        c.geom <-> ST_SetSRID(ST_MakePoint(p_longitude, p_latitude), 4326)
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Function to export isochrones as GeoJSON for a specific city center
CREATE OR REPLACE FUNCTION export_isochrones_geojson(center_name TEXT)
RETURNS TEXT AS $$
DECLARE
    result TEXT;
BEGIN
    SELECT jsonb_build_object(
        'type',     'FeatureCollection',
        'features', jsonb_agg(features.feature)
    )::text INTO result
    FROM (
        SELECT jsonb_build_object(
            'type',       'Feature',
            'id',         id,
            'geometry',   ST_AsGeoJSON(geometry)::jsonb,
            'properties', jsonb_build_object(
                'name', name,
                'value', value,
                'minutes', value/60,
                'group_index', group_index,
                'state', state,
                'zip_code', zip_code
            )
        ) AS feature
        FROM isochrones
        WHERE name = center_name
        ORDER BY value
    ) features;

    RETURN result;
END;
$$ LANGUAGE plpgsql;
