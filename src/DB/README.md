# Database Schema for IsochroneMapsV2

This directory contains SQL files for setting up and managing the Supabase database schema used by IsochroneMapsV2.

## Overview

IsochroneMapsV2 can operate in two modes:

- **Local mode**: Using CSV files and local GeoJSON storage
- **Database mode**: Using Supabase as a backend storage

When operating in database mode, the application requires specific tables and extensions to be set up in Supabase.

## SQL Files

### `schema.sql`

Contains the complete database schema definition including:

- Table definitions for city centers, locations, and isochrones
- PostGIS extension setup for spatial data handling
- Indexes for optimizing geospatial queries
- Foreign key relationships and constraints

### `functions.sql`

Contains SQL functions used by the application for:

- Geospatial calculations
- Data processing operations
- Helper functions for isochrone management

## Setup Instructions

1. **Prerequisite**: Create a Supabase project at [supabase.com](https://supabase.com)

2. **Initial Schema Setup**:

   Navigate to the SQL Editor in your Supabase dashboard and execute the contents of `schema.sql`:

   ```sql
   -- Copy and paste the entire contents of schema.sql here
   ```

3. **Install Functions**:

   Execute the functions in `functions.sql`:

   ```sql
   -- Copy and paste the entire contents of functions.sql here
   ```

4. **Configure Environment Variables**:

   Add your Supabase credentials to the `.env` file in the project root:

   ```
   SUPABASE_URL=your_project_url
   SUPABASE_KEY=your_service_role_key
   ```

## Table Structure

### City Centers Table

Stores the central locations used for generating isochrones.

Key fields:

- `id`: Unique identifier
- `address`: Street address
- `city`: City name
- `state`: State or province
- `zip_code`: ZIP/postal code
- `latitude`, `longitude`: Geographic coordinates

### Locations Table

Stores points of interest to be displayed on the maps.

Key fields:

- `id`: Unique identifier
- `name`: Location name
- `address`: Street address
- `city`: City name
- `state`: State or province
- `zip_code`: ZIP/postal code
- `latitude`, `longitude`: Geographic coordinates
- `category`: Optional location category

### Isochrones Table

Stores the generated isochrone polygons.

Key fields:

- `id`: Unique identifier
- `name`: Associated center name
- `state`: State code
- `zip_code`: ZIP/postal code
- `group_index`: Index to group related isochrones
- `value`: Time value in seconds
- `center`: Geographic center point (PostGIS geometry)
- `geometry`: Isochrone polygon (PostGIS geometry)
- `metadata`: Additional data (JSONB)

## Working with Spatial Data

The SQL files set up PostGIS extensions for:

- Storing and indexing spatial geometries
- Performing spatial operations (intersections, distances, etc.)
- Converting between geometry formats (GeoJSON, WKT, etc.)

Example query to find all locations within an isochrone:

```sql
SELECT l.*
FROM locations l, isochrones i
WHERE ST_Contains(i.geometry, ST_SetSRID(ST_Point(l.longitude, l.latitude), 4326))
AND i.name = 'CityName'
AND i.value = 1800;  -- 30 minutes (1800 seconds)
```

## Troubleshooting

If you encounter issues:

1. Verify PostGIS extension is installed correctly
2. Check that spatial indexes are created properly
3. Ensure your Supabase permissions allow the required operations
4. Validate that geometries are being stored in SRID 4326 (WGS84)

For more information, refer to the main project README or the Supabase documentation at [supabase.com/docs](https://supabase.com/docs).
