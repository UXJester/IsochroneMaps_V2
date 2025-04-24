create table
  locations (
    id bigint primary key generated always as identity, -- unique identifier for each location
    name text not null, -- point of interest name (must be unique for referencing)
    address text, -- address
    city text not null, -- city
    state text not null, -- state
    zip_code text not null, -- zip code
    latitude double precision, -- latitude
    longitude double precision, -- longitude
    error text, -- error message
    constraint location_name_key unique (name, city, state, zip_code) -- unique constraint on name, address, city, state, and zip_code
  );
