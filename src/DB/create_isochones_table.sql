create table
  isochrones (
    id bigint primary key generated always as identity, -- unique identifier for each isochrone
    name varchar(255) not null, -- links to the centers table
    state text not null,
    zip_code text not null,
    group_index int not null, -- group index from the geojson
    value float not null, -- value (e.g., travel time in seconds)
    center gis.geography (POINT, 4326) not null, -- center point as a geographic coordinate
    geometry gis.geography (POLYGON, 4326) not null, -- isochrone geometry as a polygon
    metadata jsonb, -- metadata from the geojson file
    created_at timestamp default now (), -- timestamp for record creation
    modified_at timestamp default current_timestamp, -- timestamp for last modification
    constraint isochrones_center_key unique (name, state, zip_code, value), -- unique constraint on center_name, center_state, center_zip_code and value
    constraint isochrones_name_fkey foreign key (name, state, zip_code) references city_centers (city, state, zip_code) on delete cascade -- foreign key reference to the city_centers table
  );

-- Automatically update the modified_at column on row updates
-- This function is triggered before any update to set the current timestamp
create or replace function update_modified_at_column()
returns trigger as $$
begin
   new.modified_at = current_timestamp;
   return new;
end;
$$ language plpgsql;

-- Apply the trigger to the isochrones table
create trigger set_modified_at
before update on isochrones
for each row
execute function update_modified_at_column();
