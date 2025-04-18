import json
import os
import osmnx as ox
from geopy.geocoders import Nominatim
from shapely.geometry import Point
import geopandas as gpd


class PlaceDataManager:
    def __init__(self, db_file="places_db.json"):
        self.db_file = db_file
        self.geolocator = Nominatim(user_agent="travel_live_map_app")
        self.places = self.load_places()

    def load_places(self):
        if os.path.exists(self.db_file):
            with open(self.db_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def save_places(self):
        with open(self.db_file, "w", encoding="utf-8") as f:
            json.dump(self.places, f, indent=4)

    def place_exists(self, name):
        """Check if a place with the same name already exists (case-insensitive)."""
        return any(p['name'].lower() == name.lower() for p in self.places)

    def add_place(self, name, year=None):
        """Add a new place to the database (if not already added)."""
        if any(p['name'].lower() == name.lower() for p in self.places):
            raise Exception(f"'{name}' is already added.")

        try:
            location = self.geolocator.geocode(name, geometry='geojson')
            if not location:
                raise ValueError("Could not find location")

            boundaries = None
            is_estimated_boundary = False
            try:
                city_name = name.split(',')[0].strip()
                gdf = ox.geometries_from_place(city_name, tags={'boundary': 'administrative'})
                gdf = gdf[gdf.geom_type.isin(['Polygon', 'MultiPolygon'])]
                if not gdf.empty:
                    boundaries = json.loads(gdf.geometry.iloc[0].to_json())
            except Exception as e:
                print(f"OSM boundary fetch failed: {e}")
                if 'geojson' in location.raw:
                    boundaries = location.raw['geojson']

            # Create a circular buffer if boundaries are not available or are just a point
            if not boundaries or (boundaries and boundaries.get('type') == 'Point'):
                # Create a circular buffer (5km radius) around the point
                point = Point(location.longitude, location.latitude)
                buffer = point.buffer(0.045)  # Approximately 5km at equator
                boundaries = json.loads(gpd.GeoSeries([buffer]).__geo_interface__)
                is_estimated_boundary = True

            # Get current year if none provided
            import datetime
            current_year = datetime.datetime.now().year
            visit_year = year if year else current_year

            place = {
                'name': name,
                'lat': location.latitude,
                'lon': location.longitude,
                'boundaries': boundaries,
                'year': visit_year,
                'is_estimated_boundary': is_estimated_boundary
            }
            self.places.append(place)
            self.save_places()
            return place

        except Exception as e:
            raise Exception(f"Geocoding error: {str(e)}")


    def remove_place(self, name):
        place_to_remove = next((p for p in self.places if p['name'].lower() == name.lower()), None)
        if place_to_remove:
            self.places.remove(place_to_remove)
            self.save_places()
            return True
        return False

    def get_all_places(self):
        return self.places
