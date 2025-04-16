import sys
import os
import folium
from folium import Marker, GeoJson
from geopy.geocoders import Nominatim
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QListWidget, QMessageBox
)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl
import osmnx as ox
import json


class PlaceDataManager:
    def __init__(self, db_file="places_db.json"):
        self.db_file = db_file
        self.geolocator = Nominatim(user_agent="travel_live_map_app")
        self.places = self.load_places()

    def load_places(self):
        """Load places from the custom database file (JSON)."""
        if os.path.exists(self.db_file):
            with open(self.db_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def save_places(self):
        """Save the places to the custom database file (JSON)."""
        with open(self.db_file, "w", encoding="utf-8") as f:
            json.dump(self.places, f, indent=4)

    def add_place(self, name):
        """Add a new place to the database."""
        try:
            location = self.geolocator.geocode(name, geometry='geojson')
            if not location:
                raise ValueError("Could not find location")

            boundaries = None
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

            place = {
                'name': name,
                'lat': location.latitude,
                'lon': location.longitude,
                'boundaries': boundaries
            }
            self.places.append(place)
            self.save_places()  # Save to the custom database
            return place

        except Exception as e:
            raise Exception(f"Geocoding error: {str(e)}")

    def remove_place(self, name):
        """Remove a place from the database."""
        place_to_remove = None
        for place in self.places:
            if place['name'] == name:
                place_to_remove = place
                break
        if place_to_remove:
            self.places.remove(place_to_remove)
            self.save_places()  # Save after removal
            return True
        return False

    def get_all_places(self):
        """Get all places stored in the custom database."""
        return self.places



class TravelMap:
    def __init__(self):
        self.map = folium.Map(location=[20, 0], zoom_start=2)

    def add_place(self, place):
        # Add marker
        Marker(
            location=[place['lat'], place['lon']],
            popup=f"<b>{place['name']}</b>",
            tooltip=place['name'],
            icon=folium.Icon(color="blue")
        ).add_to(self.map)

        # Add boundary polygon if available
        if place['boundaries']:
            GeoJson(
                place['boundaries'],
                style_function=lambda x: {
                    'fillColor': '#3388ff',
                    'color': '#0055cc',
                    'weight': 2,
                    'fillOpacity': 0.4
                }
            ).add_to(self.map)

    def to_html(self):
        import io
        data = io.BytesIO()
        self.map.save(data, close_file=False)
        return data.getvalue().decode()


class TravelMapApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Travel Catalog Map")
        self.setGeometry(100, 100, 1000, 600)

        self.data_manager = PlaceDataManager()
        self.travel_map = TravelMap()
        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # Sidebar
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar.setFixedWidth(300)

        sidebar_layout.addWidget(QLabel("Place (City, Country):"))
        self.place_input = QLineEdit()
        sidebar_layout.addWidget(self.place_input)

        self.add_button = QPushButton("Add Place")
        self.add_button.clicked.connect(self.add_place)
        sidebar_layout.addWidget(self.add_button)

        self.remove_button = QPushButton("Remove Place")
        self.remove_button.clicked.connect(self.remove_place)
        sidebar_layout.addWidget(self.remove_button)

        self.places_list = QListWidget()
        sidebar_layout.addWidget(self.places_list)

        main_layout.addWidget(sidebar)

        # Map view
        self.map_view = QWebEngineView()
        main_layout.addWidget(self.map_view)
        self.update_map_view()

        # Load all places into the list at startup
        self.load_places_list()

    def load_places_list(self):
        self.places_list.clear()
        for place in self.data_manager.get_all_places():
            self.places_list.addItem(place['name'])

    def update_map_view(self):
        html = self.travel_map.to_html()
        temp_file = "temp_map.html"
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(html)
        self.map_view.load(QUrl.fromLocalFile(os.path.abspath(temp_file)))

    def add_place(self):
        try:
            place_name = self.place_input.text().strip()
            if not place_name:
                QMessageBox.warning(self, "Input Error", "Place name cannot be empty.")
                return

            place = self.data_manager.add_place(place_name)
            self.travel_map.add_place(place)
            self.update_map_view()

            self.places_list.addItem(place_name)
            self.place_input.clear()

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def remove_place(self):
        selected_item = self.places_list.currentItem()
        if selected_item:
            place_name = selected_item.text()
            success = self.data_manager.remove_place(place_name)
            if success:
                self.travel_map = TravelMap()  # Reset the map
                self.load_places_list()  # Reload the places list
                self.update_map_view()
                QMessageBox.information(self, "Success", f"{place_name} removed successfully.")
            else:
                QMessageBox.warning(self, "Error", f"{place_name} not found.")
        else:
            QMessageBox.warning(self, "Selection Error", "Please select a place to remove.")



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TravelMapApp()
    window.show()
    sys.exit(app.exec_())
