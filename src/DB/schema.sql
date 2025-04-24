-- IsochroneMapsV2 Database Schema
-- This file contains the schema definition for the Supabase database

-- Enable PostGIS extension for geospatial functionality
CREATE EXTENSION IF NOT EXISTS postgis;

-- City Centers Table
-- Stores central locations for isochrone generation
CREATE TABLE IF NOT EXISTS city_centers (
    id SERIAL PRIMARY KEY,
    address TEXT,
    city TEXT NOT NULL,
    state VARCHAR(2) NOT NULL,
    zip_code VARCHAR(10),
    latitude NUMERIC(9,6) NOT NULL,
    longitude NUMERIC(9,6) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB
);

-- Index for geographic coordinates
CREATE INDEX IF NOT EXISTS idx_city_centers_coordinates
ON city_centers (latitude, longitude);

-- Create a spatial index for city centers
ALTER TABLE city_centers ADD COLUMN IF NOT EXISTS geom geometry(POINT, 4326);
CREATE INDEX IF NOT EXISTS idx_city_centers_geom ON city_centers USING GIST(geom);

-- Update trigger to maintain geometry column from lat/long
CREATE OR REPLACE FUNCTION update_city_center_geom()
RETURNS TRIGGER AS $$
BEGIN
    NEW.geom = ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_city_center_geom ON city_centers;
CREATE TRIGGER trigger_update_city_center_geom
BEFORE INSERT OR UPDATE OF latitude, longitude ON city_centers
FOR EACH ROW EXECUTE FUNCTION update_city_center_geom();

-- Locations Table
-- Stores points of interest to display on maps
CREATE TABLE IF NOT EXISTS locations (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    address TEXT,
    city TEXT,
    state VARCHAR(2),
    zip_code VARCHAR(10),
    latitude NUMERIC(9,6) NOT NULL,
    longitude NUMERIC(9,6) NOT NULL,
    category TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB
);

-- Index for geographic coordinates
CREATE INDEX IF NOT EXISTS idx_locations_coordinates
ON locations (latitude, longitude);

-- Create a spatial index for locations
ALTER TABLE locations ADD COLUMN IF NOT EXISTS geom geometry(POINT, 4326);
CREATE INDEX IF NOT EXISTS idx_locations_geom ON locations USING GIST(geom);

-- Update trigger to maintain geometry column from lat/long
CREATE OR REPLACE FUNCTION update_location_geom()
RETURNS TRIGGER AS $$
BEGIN
    NEW.geom = ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_location_geom ON locations;
CREATE TRIGGER trigger_update_location_geom
BEFORE INSERT OR UPDATE OF latitude, longitude ON locations
FOR EACH ROW EXECUTE FUNCTION update_location_geom();

-- Isochrones Table
-- Stores the generated isochrone polygons
CREATE TABLE IF NOT EXISTS isochrones (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL, -- Associated center name
    state VARCHAR(2),
    zip_code VARCHAR(10),
    group_index INTEGER NOT NULL, -- Index to group related isochrones
    value INTEGER NOT NULL, -- Time value in seconds
    center geometry(POINT, 4326) NOT NULL, -- Center point
    geometry geometry(POLYGON, 4326) NOT NULL, -- Isochrone polygon
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB
);

-- Index for value (time in seconds)
CREATE INDEX IF NOT EXISTS idx_isochrones_value ON isochrones (value);

-- Index for group
CREATE INDEX IF NOT EXISTS idx_isochrones_group ON isochrones (group_index);

-- Spatial index for center points
CREATE INDEX IF NOT EXISTS idx_isochrones_center ON isochrones USING GIST(center);

-- Spatial index for polygons
CREATE INDEX IF NOT EXISTS idx_isochrones_geometry ON isochrones USING GIST(geometry);

-- User Generated Isochrones
-- Stores isochrones created directly through the map interface
CREATE TABLE IF NOT EXISTS user_isochrones (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id), -- Link to Supabase auth
    name TEXT,
    value INTEGER NOT NULL, -- Time value in seconds
    center geometry(POINT, 4326) NOT NULL, -- Center point
    geometry geometry(POLYGON, 4326) NOT NULL, -- Isochrone polygon
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB
);

-- Spatial index for user isochrones
CREATE INDEX IF NOT EXISTS idx_user_isochrones_geometry ON user_isochrones USING GIST(geometry);

-- Update trigger for timestamps
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add timestamp triggers to tables
DROP TRIGGER IF EXISTS trigger_update_city_centers_timestamp ON city_centers;
CREATE TRIGGER trigger_update_city_centers_timestamp
BEFORE UPDATE ON city_centers
FOR EACH ROW EXECUTE FUNCTION update_modified_column();

DROP TRIGGER IF EXISTS trigger_update_locations_timestamp ON locations;
CREATE TRIGGER trigger_update_locations_timestamp
BEFORE UPDATE ON locations
FOR EACH ROW EXECUTE FUNCTION update_modified_column();

DROP TRIGGER IF EXISTS trigger_update_isochrones_timestamp ON isochrones;
CREATE TRIGGER trigger_update_isochrones_timestamp
BEFORE UPDATE ON isochrones
FOR EACH ROW EXECUTE FUNCTION update_modified_column();
