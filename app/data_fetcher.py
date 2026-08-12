"""Módulo para obtener datos sísmicos del USGS."""

import httpx
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
from app.config import USGS_BASE_URL, FEEDS


async def fetch_realtime_earthquakes(feed: str = "day_m2.5") -> dict:
    """Obtiene sismos en tiempo real desde USGS feeds."""
    url = FEEDS.get(feed)
    if not url:
        url = FEEDS["day_m2.5"]

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()


async def fetch_historical_earthquakes(
    start_date: str,
    end_date: str,
    min_magnitude: float = 2.5,
    min_latitude: Optional[float] = None,
    max_latitude: Optional[float] = None,
    min_longitude: Optional[float] = None,
    max_longitude: Optional[float] = None,
    limit: int = 20000,
) -> dict:
    """Obtiene datos históricos de sismos del catálogo USGS."""
    params = {
        "format": "geojson",
        "starttime": start_date,
        "endtime": end_date,
        "minmagnitude": min_magnitude,
        "limit": limit,
        "orderby": "time",
    }

    if min_latitude is not None:
        params["minlatitude"] = min_latitude
    if max_latitude is not None:
        params["maxlatitude"] = max_latitude
    if min_longitude is not None:
        params["minlongitude"] = min_longitude
    if max_longitude is not None:
        params["maxlongitude"] = max_longitude

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(USGS_BASE_URL, params=params)
        response.raise_for_status()
        return response.json()


def geojson_to_dataframe(geojson_data: dict) -> pd.DataFrame:
    """Convierte datos GeoJSON de USGS a DataFrame."""
    features = geojson_data.get("features", [])

    if not features:
        return pd.DataFrame()

    records = []
    for feature in features:
        props = feature.get("properties", {})
        coords = feature.get("geometry", {}).get("coordinates", [0, 0, 0])

        records.append({
            "id": feature.get("id", ""),
            "magnitude": props.get("mag"),
            "place": props.get("place", ""),
            "time": props.get("time"),
            "updated": props.get("updated"),
            "tz": props.get("tz"),
            "url": props.get("url", ""),
            "detail": props.get("detail", ""),
            "felt": props.get("felt"),
            "cdi": props.get("cdi"),
            "mmi": props.get("mmi"),
            "alert": props.get("alert"),
            "status": props.get("status", ""),
            "tsunami": props.get("tsunami", 0),
            "sig": props.get("sig", 0),
            "net": props.get("net", ""),
            "code": props.get("code", ""),
            "nst": props.get("nst"),
            "dmin": props.get("dmin"),
            "rms": props.get("rms"),
            "gap": props.get("gap"),
            "mag_type": props.get("magType", ""),
            "type": props.get("type", ""),
            "longitude": coords[0] if len(coords) > 0 else None,
            "latitude": coords[1] if len(coords) > 1 else None,
            "depth": coords[2] if len(coords) > 2 else None,
        })

    df = pd.DataFrame(records)

    # Convertir timestamp a datetime
    if "time" in df.columns and not df.empty:
        df["datetime"] = pd.to_datetime(df["time"], unit="ms", utc=True)
        df["date"] = df["datetime"].dt.date
        df["hour"] = df["datetime"].dt.hour
        df["day_of_week"] = df["datetime"].dt.dayofweek
        df["month"] = df["datetime"].dt.month
        df["year"] = df["datetime"].dt.year

    return df


async def get_training_data(years_back: int = 5, min_magnitude: float = 2.5) -> pd.DataFrame:
    """Obtiene datos históricos para entrenamiento del modelo."""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=years_back * 365)

    all_data = []
    # Obtener datos por año para evitar límites de la API
    current_start = start_date

    while current_start < end_date:
        current_end = min(current_start + timedelta(days=365), end_date)

        try:
            data = await fetch_historical_earthquakes(
                start_date=current_start.strftime("%Y-%m-%d"),
                end_date=current_end.strftime("%Y-%m-%d"),
                min_magnitude=min_magnitude,
            )
            df = geojson_to_dataframe(data)
            if not df.empty:
                all_data.append(df)
        except Exception as e:
            print(f"Error obteniendo datos para {current_start.date()} - {current_end.date()}: {e}")

        current_start = current_end

    if all_data:
        return pd.concat(all_data, ignore_index=True)
    return pd.DataFrame()
