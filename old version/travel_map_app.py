import sys
import os
import folium
from folium import GeoJson
from geopy.geocoders import Nominatim
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QListWidget, QMessageBox,
    QFrame, QSplitter, QListWidgetItem
)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, Qt
from PyQt5.QtGui import QFont
import osmnx as ox
import json
import pickle
import tempfile
import requests
import pycountry
from fuzzywuzzy import process
import geopandas as gpd
from shapely.geometry import Point
from style_manager import StyleManager

class PlaceDataManager:
    """Manages place data persistence and retrieval"""

    def __init__(self, db_file="places_db.json", boundaries_file=r"C:\Users\Jalpan\Desktop\digina\data\india_boundaries.gpkg"):
        self.db_file = db_file
        self.geolocator = Nominatim(user_agent="travel_live_map_app")
        self.places = self.load_places()
        self.geocode_cache = self.load_geocode_cache()
        # Load local boundaries dataset and discover available layers
        self.boundaries_file = boundaries_file
        self.boundaries_gdfs = {}
        try:
            # Discover all layers in the GeoPackage
            layers = gpd.list_layers(boundaries_file)
            layer_names = layers['name'].tolist()
            print(f"Available layers in GeoPackage: {layer_names}")
            # Define layer priority and expected names
            layer_priority = [
                ('ADM_ADM_0', 0),  # Country-level
                ('ADM_ADM_2', 2),  # District-level
                ('ADM_ADM_1', 1),  # State/region-level
                ('ADM_ADM_3', 3)   # Sub-district-level
            ]
            for layer_name, adm_level in layer_priority:
                if layer_name in layer_names:
                    try:
                        gdf = gpd.read_file(boundaries_file, layer=layer_name, columns=['NAME_2', 'NAME_1', 'NAME_0', 'geometry'])
                        # Simplify geometries to reduce memory usage
                        gdf['geometry'] = gdf['geometry'].simplify(tolerance=0.001, preserve_topology=True)
                        self.boundaries_gdfs[layer_name] = gdf
                        print(f"Loaded layer '{layer_name}' with {len(gdf)} features")
                        print(f"Columns in layer '{layer_name}': {list(gdf.columns)}")
                    except Exception as e:
                        print(f"Error loading layer '{layer_name}': {e}")
            if not self.boundaries_gdfs:
                print("No valid layers loaded from GeoPackage")
        except Exception as e:
            print(f"Error accessing GeoPackage: {e}")
            self.boundaries_gdfs = {}

    def load_places(self):
        """Load places from the custom database file (JSON)."""
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print(f"Error decoding JSON from {self.db_file}")
                return []
        return []

    def save_places(self):
        """Save the places to the custom database file (JSON)."""
        try:
            with open(self.db_file, "w", encoding="utf-8") as f:
                json.dump(self.places, f, indent=4)
        except Exception as e:
            print(f"Error saving places: {e}")

    def load_geocode_cache(self):
        """Load geocoding cache from file."""
        cache_file = "geocode_cache.pkl"
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "rb") as f:
                    return pickle.load(f)
            except:
                return {}
        return {}

    def save_geocode_cache(self):
        """Save geocoding cache to file."""
        try:
            with open("geocode_cache.pkl", "wb") as f:
                pickle.dump(self.geocode_cache, f)
        except Exception as e:
            print(f"Error saving geocode cache: {e}")

    def add_place(self, name, year=None):
        """Add a new place to the database using multiple data sources, merging geopy results."""
        try:
            # Check geocoding cache
            name_key = name.lower()
            if name_key in self.geocode_cache:
                location = self.geocode_cache[name_key]
            else:
                location = self.geolocator.geocode(name, geometry='geojson')
                if location:
                    self.geocode_cache[name_key] = location
                    self.save_geocode_cache()
                else:
                    raise ValueError(f"Could not find location: {name}")

            city_name = name.split(',')[0].strip()
            country_name = name.split(',')[-1].strip() if ',' in name else city_name
            point = Point(location.longitude, location.latitude)
            print(f"Searching boundaries for {city_name}")

            # Store results from all sources
            boundary_results = []

            # 1. geoBoundaries API (district-level, ADM2)
            try:
                country = pycountry.countries.search_fuzzy(country_name)[0]
                iso3_code = country.alpha_3
                api_url = f"https://www.geoboundaries.org/api/current/gbOpen/{iso3_code}/ADM2/"
                response = requests.get(api_url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('gjDownloadURL'):
                        gdf = gpd.read_file(data['gjDownloadURL'])
                        print(f"geoBoundaries: Checking {len(gdf)} ADM2 boundaries")
                        # Point-in-polygon check
                        for idx, row in gdf.iterrows():
                            if row.geometry.contains(point):
                                boundary_results.append({
                                    'source': 'geoBoundaries',
                                    'geometry': row.geometry.__geo_interface__,
                                    'score': 90 if row.geometry.contains(point) else 70,
                                    'name': row.get('shapeName', city_name)
                                })
                                print(f"geoBoundaries: Found boundary (point-in-polygon)")
                                break
                        # Fuzzy match if point-based search fails
                        if not any(r['source'] == 'geoBoundaries' for r in boundary_results) and 'shapeName' in gdf.columns:
                            names = gdf['shapeName'].str.lower().tolist()
                            match = process.extractOne(city_name.lower(), names, score_cutoff=80)
                            if match:
                                boundary_results.append({
                                    'source': 'geoBoundaries',
                                    'geometry': gdf[gdf['shapeName'].str.lower() == match[0]].geometry.iloc[0].__geo_interface__,
                                    'score': 70,
                                    'name': match[0]
                                })
                                print(f"geoBoundaries: Found boundary (fuzzy match: {match[0]})")
            except Exception as e:
                print(f"geoBoundaries fetch failed: {e}")

            # 2. Local boundaries dataset (check layers in order: ADM0, ADM2, ADM1, ADM3)
            if self.boundaries_gdfs:
                layer_priority = ['ADM_ADM_0', 'ADM_ADM_2', 'ADM_ADM_1', 'ADM_ADM_3']
                for layer_name in layer_priority:
                    if layer_name in self.boundaries_gdfs:
                        try:
                            gdf = self.boundaries_gdfs[layer_name]
                            print(f"Local dataset ({layer_name}): Checking {len(gdf)} boundaries")
                            # Determine name column based on layer
                            name_col = 'NAME_2' if layer_name == 'ADM_ADM_2' else 'NAME_1' if layer_name == 'ADM_ADM_1' else 'NAME_0' if layer_name == 'ADM_ADM_0' else 'NAME_3'
                            # Point-in-polygon check
                            for idx, row in gdf.iterrows():
                                if row.geometry.contains(point):
                                    score = {
                                        'ADM_ADM_0': 80,
                                        'ADM_ADM_2': 85,
                                        'ADM_ADM_1': 82,
                                        'ADM_ADM_3': 78
                                    }.get(layer_name, 65)
                                    boundary_results.append({
                                        'source': f'Local dataset ({layer_name})',
                                        'geometry': row.geometry.__geo_interface__,
                                        'score': score if row.geometry.contains(point) else score - 20,
                                        'name': row.get(name_col, city_name)
                                    })
                                    print(f"Local dataset ({layer_name}): Found boundary (point-in-polygon)")
                                    break
                            # Fuzzy match if point-based search fails
                            if not any(r['source'] == f'Local dataset ({layer_name})' for r in boundary_results) and name_col in gdf.columns:
                                names = gdf[name_col].str.lower().tolist()
                                match = process.extractOne(city_name.lower(), names, score_cutoff=80)
                                if match:
                                    score = {
                                        'ADM_ADM_0': 60,
                                        'ADM_ADM_2': 65,
                                        'ADM_ADM_1': 62,
                                        'ADM_ADM_3': 58
                                    }.get(layer_name, 45)
                                    boundary_results.append({
                                        'source': f'Local dataset ({layer_name})',
                                        'geometry': gdf[gdf[name_col].str.lower() == match[0]].geometry.iloc[0].__geo_interface__,
                                        'score': score,
                                        'name': match[0]
                                    })
                                    print(f"Local dataset ({layer_name}): Found boundary (fuzzy match: {match[0]})")
                        except Exception as e:
                            print(f"Local dataset ({layer_name}) fetch failed: {e}")

            # 3. OSM boundaries
            try:
                gdf = ox.geometries_from_place(city_name, tags={'boundary': 'administrative'})
                gdf = gdf[gdf.geom_type.isin(['Polygon', 'MultiPolygon'])]
                if not gdf.empty:
                    print(f"OSM: Checking {len(gdf)} boundaries")
                    # Point-in-polygon check
                    for idx, row in gdf.iterrows():
                        if row.geometry.contains(point):
                            boundary_results.append({
                                'source': 'OSM',
                                'geometry': row.geometry.__geo_interface__,
                                'score': 80 if row.geometry.contains(point) else 60,
                                'name': row.get('name', city_name)
                            })
                            print(f"OSM: Found boundary (point-in-polygon)")
                            break
                    # Take first valid boundary if point-based search fails
                    if not any(r['source'] == 'OSM' for r in boundary_results):
                        boundary_results.append({
                            'source': 'OSM',
                            'geometry': gdf.geometry.iloc[0].__geo_interface__,
                            'score': 60,
                            'name': gdf.get('name', city_name)
                        })
                        print(f"OSM: Found boundary (first available)")
            except Exception as e:
                print(f"OSM boundary fetch failed: {e}")

            # 4. geopy GeoJSON
            try:
                if 'geojson' in location.raw and location.raw['geojson'].get('type') in ['Polygon', 'MultiPolygon']:
                    boundary_results.append({
                        'source': 'geopy',
                        'geometry': location.raw['geojson'],
                        'score': 75 if Point(location.longitude, location.latitude).within(gpd.GeoSeries([location.raw['geojson']]).iloc[0]) else 55,
                        'name': city_name
                    })
                    print(f"geopy: Found boundary (GeoJSON)")
                else:
                    print(f"geopy GeoJSON is a {location.raw['geojson'].get('type') if 'geojson' in location.raw else 'missing'}, not a valid boundary")
            except Exception as e:
                print(f"geopy GeoJSON processing failed: {e}")

            # Select the best boundary
            if boundary_results:
                # Sort by score (higher is better)
                best_result = max(boundary_results, key=lambda x: x['score'])
                boundaries = best_result['geometry']
                source = best_result['source']
                print(f"Selected boundary from {source} with score {best_result['score']}")
            else:
                raise ValueError(f"Could not find boundaries for {name}")

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
                'is_estimated_boundary': False,
                'boundary_source': source
            }
            self.places.append(place)
            self.save_places()
            return place

        except Exception as e:
            raise Exception(str(e))

    def remove_place(self, name):
        """Remove a place from the database."""
        place_to_remove = None
        for place in self.places:
            if place['name'] == name:
                place_to_remove = place
                break
        if place_to_remove:
            self.places.remove(place_to_remove)
            self.save_places()
            return True
        return False

    def get_all_places(self):
        """Get all places stored in the custom database."""
        return self.places

class TravelMap:
    """Manages the folium map and its features"""

    def __init__(self, dark_mode=False):
        self.dark_mode = dark_mode
        self.map = self._create_map()

    def _create_map(self):
        """Create a new map with appropriate styling based on mode"""
        if self.dark_mode:
            return folium.Map(
                location=[20, 0],
                zoom_start=2,
                tiles="cartodbdark_matter",
                control_scale=True
            )
        else:
            return folium.Map(
                location=[20, 0],
                zoom_start=2,
                control_scale=True
            )

    def reset(self):
        """Reset the map to initial state"""
        self.map = self._create_map()

    def add_place(self, place):
        """Add a place to the map with boundaries only"""
        if place['boundaries']:
            color = '#46CDCF' if self.dark_mode else '#3388ff'
            fill_color = '#19647E' if self.dark_mode else '#3388ff'
            dash_array = None
            weight = 2

            GeoJson(
                place['boundaries'],
                style_function=lambda x: {
                    'fillColor': fill_color,
                    'color': color,
                    'weight': weight,
                    'fillOpacity': 0.4,
                    'dashArray': dash_array
                }
            ).add_to(self.map)

    def add_all_places(self, places):
        """Add all places to the map"""
        self.reset()
        for place in places:
            self.add_place(place)

    def to_html(self):
        """Convert map to HTML for display"""
        import io
        data = io.BytesIO()
        self.map.save(data, close_file=False)
        return data.getvalue().decode()

class TravelMapApp(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Travel Catalog Map")
        self.setGeometry(100, 100, 1200, 700)
        self.dark_mode = False
        self.data_manager = PlaceDataManager()
        self.travel_map = TravelMap(dark_mode=self.dark_mode)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_map_path = os.path.join(self.temp_dir.name, "temp_map.html")
        self.init_ui()
        self.load_places_and_update_map()

    def init_ui(self):
        """Initialize the user interface"""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar_frame")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(15, 15, 15, 15)
        sidebar_layout.setSpacing(10)

        title_label = QLabel("Travel Catalog")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        sidebar_layout.addWidget(title_label)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        sidebar_layout.addWidget(separator)

        sidebar_layout.addWidget(QLabel("Add New Location:"))
        self.place_input = QLineEdit()
        self.place_input.setPlaceholderText("City, Country")
        self.place_input.returnPressed.connect(self.add_place)
        sidebar_layout.addWidget(self.place_input)

        sidebar_layout.addWidget(QLabel("Year of Visit (optional):"))
        self.year_input = QLineEdit()
        self.year_input.setPlaceholderText("Current year will be used if empty")
        self.year_input.returnPressed.connect(self.add_place)
        sidebar_layout.addWidget(self.year_input)

        buttons_layout = QHBoxLayout()
        self.add_button = QPushButton("Add")
        self.add_button.setMinimumHeight(30)
        self.add_button.clicked.connect(self.add_place)
        buttons_layout.addWidget(self.add_button)

        self.remove_button = QPushButton("Remove")
        self.remove_button.setMinimumHeight(30)
        self.remove_button.clicked.connect(self.remove_place)
        buttons_layout.addWidget(self.remove_button)
        sidebar_layout.addLayout(buttons_layout)

        sidebar_layout.addWidget(QLabel("Your Places:"))
        self.places_list = QListWidget()
        self.places_list.setAlternatingRowColors(True)
        self.places_list.setSelectionMode(QListWidget.SingleSelection)
        self.places_list.itemClicked.connect(self.place_selected)
        sidebar_layout.addWidget(self.places_list)

        self.stats_label = QLabel("Total Places: 0")
        sidebar_layout.addWidget(self.stats_label)

        separator2 = QFrame()
        separator2.setFrameShape(QFrame.HLine)
        separator2.setFrameShadow(QFrame.Sunken)
        sidebar_layout.addWidget(separator2)

        self.theme_button = QPushButton("Toggle Light/Dark Mode")
        self.theme_button.setMinimumHeight(30)
        self.theme_button.clicked.connect(self.toggle_theme)
        sidebar_layout.addWidget(self.theme_button)

        splitter.addWidget(sidebar)
        map_container = QWidget()
        map_layout = QVBoxLayout(map_container)
        map_layout.setContentsMargins(0, 0, 0, 0)
        self.map_view = QWebEngineView()
        map_layout.addWidget(self.map_view)
        splitter.addWidget(map_container)
        splitter.setSizes([300, 900])
        main_layout.addWidget(splitter)

    def load_places_list(self):
        """Load places into the list widget"""
        self.places_list.clear()
        places = self.data_manager.get_all_places()
        for place in places:
            display_text = place['name']
            if 'year' in place:
                display_text = f"{display_text} ({place['year']})"
            item = QListWidgetItem(display_text)
            tooltip = f"Lat: {place['lat']}, Lon: {place['lon']}"
            item.setToolTip(tooltip)
            self.places_list.addItem(item)
        self.stats_label.setText(f"Total Places: {len(places)}")

    def load_places_and_update_map(self):
        """Load all places into both list and map"""
        places = self.data_manager.get_all_places()
        self.travel_map.add_all_places(places)
        self.load_places_list()
        self.update_map_view()

    def update_map_view(self):
        """Update the map in the WebEngineView"""
        html = self.travel_map.to_html()
        with open(self.temp_map_path, "w", encoding="utf-8") as f:
            f.write(html)
        self.map_view.load(QUrl.fromLocalFile(os.path.abspath(self.temp_map_path)))

    def add_place(self):
        """Add a new place to the database and map"""
        try:
            place_name = self.place_input.text().strip().upper()
            if not place_name:
                QMessageBox.warning(self, "Input Error", "Place name cannot be empty.")
                return

            year_text = self.year_input.text().strip()
            year = None
            if year_text:
                try:
                    year = int(year_text)
                except ValueError:
                    QMessageBox.warning(self, "Input Error", "Year must be a valid number.")
                    return

            self.statusBar().showMessage("Locating place... This may take a moment.")
            QApplication.processEvents()

            place = self.data_manager.add_place(place_name, year)
            self.travel_map.add_place(place)
            self.update_map_view()

            self.place_input.clear()
            self.year_input.clear()
            self.load_places_list()
            self.stats_label.setText(f"Total Places: {len(self.data_manager.get_all_places())}")
            self.statusBar().showMessage(f"Added {place_name} successfully!", 3000)

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            self.statusBar().clearMessage()

    def remove_place(self):
        """Remove a selected place"""
        selected_item = self.places_list.currentItem()
        if selected_item:
            display_text = selected_item.text()
            place_name = display_text
            if "(" in display_text:
                place_name = display_text.split("(")[0].strip()

            reply = QMessageBox.question(
                self,
                "Confirm Removal",
                f"Are you sure you want to remove {display_text}?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                success = self.data_manager.remove_place(place_name)
                if success:
                    self.load_places_and_update_map()
                    self.statusBar().showMessage(f"{display_text} removed successfully.", 3000)
                else:
                    QMessageBox.warning(self, "Error", f"{display_text} not found.")
        else:
            QMessageBox.warning(self, "Selection Error", "Please select a place to remove.")

    def place_selected(self, item):
        """Handle place selection in list"""
        self.statusBar().showMessage(f"Selected: {item.text()}", 2000)

    def toggle_theme(self):
        """Toggle between dark and light themes"""
        self.dark_mode = not self.dark_mode
        app = QApplication.instance()
        if self.dark_mode:
            StyleManager.apply_dark_theme(app)
        else:
            StyleManager.apply_light_theme(app)
        self.travel_map = TravelMap(dark_mode=self.dark_mode)
        self.load_places_and_update_map()
        theme_name = "Dark" if self.dark_mode else "Light"
        self.statusBar().showMessage(f"Switched to {theme_name} theme", 3000)

    def closeEvent(self, event):
        """Clean up temporary files on exit"""
        try:
            self.temp_dir.cleanup()
        except:
            pass
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TravelMapApp()
    StyleManager.apply_light_theme(app)
    window.show()
    sys.exit(app.exec_())