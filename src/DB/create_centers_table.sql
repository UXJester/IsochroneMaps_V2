create table
  city_centers (
    id bigint primary key generated always as identity, -- unique identifier for each city center
    address text, -- address (if available)
    city text not null, -- city
    state text not null, -- state
    zip_code text not null, -- zip code
    latitude float8, -- latitude
    longitude float8, -- longitude
    error text, -- error message
    constraint city_name_key unique (city, state, zip_code) -- unique constraint on address, city, state, and zip_code
  );
