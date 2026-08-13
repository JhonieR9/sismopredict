"""Configuración de la aplicación."""

# USGS Earthquake API
USGS_BASE_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
USGS_FEED_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary"

# Feeds disponibles de USGS (GeoJSON)
FEEDS = {
    "hour_significant": f"{USGS_FEED_URL}/significant_hour.geojson",
    "hour_m4.5": f"{USGS_FEED_URL}/4.5_hour.geojson",
    "hour_m2.5": f"{USGS_FEED_URL}/2.5_hour.geojson",
    "hour_m1.0": f"{USGS_FEED_URL}/1.0_hour.geojson",
    "day_significant": f"{USGS_FEED_URL}/significant_day.geojson",
    "day_m4.5": f"{USGS_FEED_URL}/4.5_day.geojson",
    "day_m2.5": f"{USGS_FEED_URL}/2.5_day.geojson",
    "day_m1.0": f"{USGS_FEED_URL}/1.0_day.geojson",
    "week_significant": f"{USGS_FEED_URL}/significant_week.geojson",
    "week_m4.5": f"{USGS_FEED_URL}/4.5_week.geojson",
    "week_m2.5": f"{USGS_FEED_URL}/2.5_week.geojson",
    "month_significant": f"{USGS_FEED_URL}/significant_month.geojson",
    "month_m4.5": f"{USGS_FEED_URL}/4.5_month.geojson",
    "month_m2.5": f"{USGS_FEED_URL}/2.5_month.geojson",
}

# Configuración del modelo de predicción
MODEL_PATH = "app/models/earthquake_predictor.joblib"
PREDICTION_GRID_SIZE = 2.0  # Grados para dividir el grid de predicción
PREDICTION_DAYS_AHEAD = 30  # Días a futuro para predicción

# Regiones de interés predefinidas
REGIONS = {
    "global": {"min_lat": -90, "max_lat": 90, "min_lon": -180, "max_lon": 180},
    "mexico": {"min_lat": 14, "max_lat": 33, "min_lon": -118, "max_lon": -86},
    "colombia": {"min_lat": -4, "max_lat": 13, "min_lon": -82, "max_lon": -67},
    "chile": {"min_lat": -56, "max_lat": -17, "min_lon": -76, "max_lon": -66},
    "peru": {"min_lat": -18, "max_lat": 0, "min_lon": -81, "max_lon": -68},
    "ecuador": {"min_lat": -5, "max_lat": 2, "min_lon": -81, "max_lon": -75},
    "japon": {"min_lat": 24, "max_lat": 46, "min_lon": 122, "max_lon": 146},
    "california": {"min_lat": 32, "max_lat": 42, "min_lon": -125, "max_lon": -114},
    "indonesia": {"min_lat": -11, "max_lat": 6, "min_lon": 95, "max_lon": 141},
}

# Configuración del scheduler
UPDATE_INTERVAL_MINUTES = 5
