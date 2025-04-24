# IsochroneMapsV2

A Python-based toolkit for generating and visualizing isochrone maps - areas reachable within specific travel times or distances from central locations.

## Overview

IsochroneMapsV2 provides a complete workflow for creating interactive isochrone visualizations. It handles geocoding of locations, generation of isochrone polygons via the OpenRouteService API, and creation of interactive web maps with measurement tools and custom controls.

## Features

- **Geocoding**: Convert addresses to geographic coordinates
- **Isochrone Generation**: Calculate reachable areas based on travel time/distance
- **Interactive Maps**: Create HTML maps with multiple visualization layers
- **Drawing Tools**: Measure distances, areas, and create custom shapes
- **Custom Isochrone Creation**: Generate new isochrones directly from the map interface
- **Database Integration**: Optional storage and retrieval from Supabase

## Prerequisites

- Python 3.x installed on your system
- An API key from [OpenRouteService](https://openrouteservice.org/)
- Optionally, a Supabase account for database storage

### Obtaining an OpenRouteService API Key

1. Go to [OpenRouteService](https://openrouteservice.org/)
2. Sign up for a free account or log in if you already have one
3. Navigate to the "API Keys" section in your account dashboard
4. Create a new API key and copy it for later use

## Project Structure

```
IsochroneMapsV2/
├── src/                   # Core source code
│   ├── config/            # Configuration settings
│   ├── DB/                # Database schema definitions
│   ├── static/            # Web assets
│   │   ├── css/           # Custom styling
│   │   ├── js/            # JavaScript functionality
│   │   └── images/        # Image resources
│   └── utils/             # Utility modules
├── data/                  # Data storage
│   ├── isochrones/        # Generated GeoJSON files
│   └── locations/         # CSV location data
├── maps/                  # Generated HTML map files
└── logs/                  # Application logs
```

## Installation

### Standard Installation

1. Clone the repository
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a `.env` file with required API keys:
   ```
   ORS_API_KEY=your_openrouteservice_key
   SUPABASE_URL=your_supabase_url  # Optional
   SUPABASE_KEY=your_supabase_key  # Optional
   ```

### Alternative Installation Using setup_env.py

The project includes an interactive setup script that automates the environment creation process:

1. Clone the repository
2. Run the setup script:
   ```bash
   python setup_env.py
   ```
3. Follow the interactive prompts to:

   - Create a virtual environment (in `.venv` directory)
   - Upgrade pip if needed
   - Install security certificates if required
   - Generate or use existing requirements.txt
   - Install all dependencies
   - Check for and update outdated packages

   For non-interactive setup with default options:

   ```bash
   python setup_env.py --non-interactive
   ```

4. Create a `.env` file with required API keys as described above

## Quick Start (TL;DR)

For those who want to get up and running quickly:

```bash
# Clone repository
git clone https://github.com/username/IsochroneMapsV2.git
cd IsochroneMapsV2

# Create virtual environment and activate it
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up OpenRouteService API key (optional, but add isochrones button won't work without it)
echo "ORS_API_KEY=your_openrouteservice_key" > .env

# Generate a demo map
python main.py
```

## Usage Workflow

The project follows a four-step workflow:

### 1. Prepare CSV Data

Place your location data in the `data/locations` directory:

- `cities.csv`: Central locations for isochrone generation
- `poi.csv`: Points of interest to display on maps

### 2. Geocode Locations

Run the geocoding script to convert addresses to coordinates:

```bash
python -m src.geocode
```

This will:

- Process CSV files from `data/locations`
- Use Nominatim (OpenStreetMap) for geocoding
- Generate `geocoded_*.csv` files with coordinates
- Log errors for manual correction

### 3. Generate Isochrones

Generate isochrone polygons for geocoded locations:

```bash
python -m src.isochrone
```

This will:

- Use the OpenRouteService API to calculate reachable areas
- Generate GeoJSON files in `data/isochrones`
- Optionally store data in Supabase database

### 4. Create Interactive Maps

Generate HTML maps with all visualization layers:

```bash
python -m src.maps
```

This will:

- Create HTML files in the `maps` directory
- Include interactive features (zooming, drawing tools, layer controls)
- Implement custom tooltips and measurement calculations

_Note:_ `geocode`, `isochrone`, and `map` modules all make use of `use-db` and `use-local` modes to allow the project to use local data instead of a database connection.

## Module Modes

IsochroneMapsV2 can operate in two different modes:

### Local Mode (Default)

By default, the project runs in `use-local` mode, which:

- Stores isochrones as GeoJSON files in `data/isochrones/`
- Loads location data from CSV files in `data/locations/`
- Requires no database setup
- Best for quick setup and local development

To explicitly use local mode:

```bash
python -m src.isochrone --mode use-local
```

### Database Mode

For more advanced use cases, the project can run in `use-db` mode, which:

- Stores and retrieves data from a Supabase database
- Enables more complex spatial queries and data management
- Supports user-generated isochrones and multi-user scenarios
- Requires Supabase setup with PostGIS extension

To use database mode:

```bash
python src.isochrone --mode use-db
```

#### Database Setup Requirements

Before using `use-db` mode:

1. Create a Supabase project and set up the database schema
2. Configure your `.env` file with Supabase credentials
3. Execute the SQL scripts as described in `src/DB/README.md`

See [Database Schema Setup](/src/DB/README.md) for detailed instructions on setting up the required database tables and functions.

## Map Functionality

The generated maps include:

- **Multiple Base Layers**: OpenStreetMap, CartoDB, Satellite, Dark, Topographic
- **Interactive Layers**: Toggle visibility of isochrones, city centers, and points of interest
- **Drawing Tools**:
  - Polylines: Display distance in miles
  - Polygons/Rectangles: Display area in acres
  - Circles: Display radius in miles
  - Markers: Display coordinates
- **Custom Isochrone Button**: Generate isochrones anywhere on the map (only available using `python main.py`)

## Configuration

Map appearance and behavior is controlled through `src/config/__init__.py`:

- `MAP_SETTINGS["zoom"]`: Default zoom level
- `MAP_SETTINGS["colors"]`: Color palette for map features
- `MAP_SETTINGS["layers"]`: Layer configuration
- `MAP_SETTINGS["tiles"]`: Tile provider settings

## Debugging

For debugging Python scripts:

1. Ensure the virtual environment is activated
2. Use the Python debugger:
   ```bash
   python -m pdb src/script_name.py
   ```
3. Or configure VS Code for debugging (see [Python debugging in VS Code](https://code.visualstudio.com/docs/python/debugging))

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request with your changes.

## License

This project is licensed under the MIT License. See the LICENSE file for details.
