"""API principal de la aplicación de predicción sísmica."""

from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional
import os

from app.data_fetcher import (
    fetch_realtime_earthquakes,
    fetch_historical_earthquakes,
    geojson_to_dataframe,
    get_training_data,
)
from app.predictor import predictor
from app.live_monitor import monitor
from app.config import REGIONS, FEEDS, MODEL_PATH


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicialización al arrancar la app."""
    print("🌍 Iniciando SismoPredict...")
    # Intentar cargar modelo existente
    if predictor.load_model():
        print("✅ Modelo de predicción cargado.")
    else:
        print("⚠️ No se encontró modelo. Entrenando automáticamente...")
        # Entrenar con 1 año de datos para que sea rápido al arrancar
        try:
            df = await get_training_data(years_back=1, min_magnitude=3.0)
            if not df.empty:
                predictor.train(df)
                print(f"✅ Modelo entrenado automáticamente con {len(df)} sismos.")
            else:
                print("⚠️ No se pudieron obtener datos para entrenamiento automático.")
        except Exception as e:
            print(f"⚠️ Error en entrenamiento automático: {e}")
    # Iniciar monitor en vivo
    await monitor.start()
    yield
    await monitor.stop()
    print("👋 SismoPredict detenido.")


app = FastAPI(
    title="SismoPredict",
    description="Sistema profesional de monitoreo y predicción sísmica con Machine Learning",
    version="1.0.0",
    lifespan=lifespan,
)

# Configurar archivos estáticos y templates
from pathlib import Path

# Determinar directorio raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent
static_dir = BASE_DIR / "static"
templates_dir = BASE_DIR / "templates"

# Fallback: si no existe templates, buscar en /app
if not templates_dir.exists():
    BASE_DIR = Path("/app")
    static_dir = BASE_DIR / "static"
    templates_dir = BASE_DIR / "templates"

static_dir.mkdir(parents=True, exist_ok=True)
templates_dir.mkdir(parents=True, exist_ok=True)

print(f"📂 BASE_DIR: {BASE_DIR}")
print(f"📂 Templates: {templates_dir} (exists: {templates_dir.exists()})")

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(templates_dir))


# ============ PAGES ============

@app.get("/health")
async def health_check():
    """Health check para Railway."""
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Página principal - Dashboard."""
    try:
        return templates.TemplateResponse(request, "dashboard.html")
    except Exception as e:
        return HTMLResponse(f"<h1>Error</h1><pre>{e}</pre><p>Templates dir: {templates_dir}</p><p>Files: {list(templates_dir.iterdir()) if templates_dir.exists() else 'DIR NOT FOUND'}</p>")


# ============ API ENDPOINTS ============

@app.get("/api/earthquakes/realtime")
async def get_realtime_earthquakes(
    feed: str = Query(default="day_m2.5", description="Feed de USGS a consultar")
):
    """Obtiene sismos en tiempo real."""
    try:
        data = await fetch_realtime_earthquakes(feed)
        df = geojson_to_dataframe(data)

        earthquakes = []
        for _, row in df.iterrows():
            earthquakes.append({
                "id": row.get("id", ""),
                "magnitude": row.get("magnitude"),
                "place": row.get("place", ""),
                "time": str(row.get("datetime", "")),
                "latitude": row.get("latitude"),
                "longitude": row.get("longitude"),
                "depth": row.get("depth"),
                "tsunami": row.get("tsunami", 0),
                "sig": row.get("sig", 0),
                "alert": row.get("alert"),
                "url": row.get("url", ""),
            })

        return {
            "status": "success",
            "count": len(earthquakes),
            "feed": feed,
            "timestamp": datetime.utcnow().isoformat(),
            "earthquakes": earthquakes,
        }
    except Exception as e:
        print(f"⚠️ Error en realtime: {e}")
        return {"status": "success", "count": 0, "feed": feed, "timestamp": datetime.utcnow().isoformat(), "earthquakes": []}


@app.get("/api/earthquakes/historical")
async def get_historical_earthquakes(
    days_back: int = Query(default=30, ge=1, le=365),
    min_magnitude: float = Query(default=4.0, ge=0, le=10),
    region: Optional[str] = Query(default=None),
):
    """Obtiene datos históricos de sismos."""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)

        kwargs = {
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "min_magnitude": min_magnitude,
        }

        if region and region in REGIONS:
            r = REGIONS[region]
            kwargs.update({
                "min_latitude": r["min_lat"],
                "max_latitude": r["max_lat"],
                "min_longitude": r["min_lon"],
                "max_longitude": r["max_lon"],
            })

        data = await fetch_historical_earthquakes(**kwargs)
        df = geojson_to_dataframe(data)

        earthquakes = []
        for _, row in df.iterrows():
            earthquakes.append({
                "id": row.get("id", ""),
                "magnitude": row.get("magnitude"),
                "place": row.get("place", ""),
                "time": str(row.get("datetime", "")),
                "latitude": row.get("latitude"),
                "longitude": row.get("longitude"),
                "depth": row.get("depth"),
                "sig": row.get("sig", 0),
            })

        return {
            "status": "success",
            "count": len(earthquakes),
            "period": f"{days_back} days",
            "region": region or "global",
            "earthquakes": earthquakes,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/train")
async def train_model(
    years_back: int = Query(default=3, ge=1, le=10),
    min_magnitude: float = Query(default=2.5, ge=0, le=5),
):
    """Entrena el modelo de predicción con datos históricos."""
    try:
        print(f"Obteniendo {years_back} años de datos históricos...")
        df = await get_training_data(years_back=years_back, min_magnitude=min_magnitude)

        if df.empty:
            return {"status": "error", "message": "No se pudieron obtener datos de entrenamiento"}

        print(f"Datos obtenidos: {len(df)} sismos. Iniciando entrenamiento...")
        metrics = predictor.train(df)

        return {
            "status": "success",
            "message": "Modelo entrenado exitosamente",
            "data_points": len(df),
            "metrics": metrics,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/predict")
async def get_predictions(
    region: Optional[str] = Query(default=None),
    days_back: int = Query(default=90, ge=30, le=365),
    min_magnitude: float = Query(default=2.5, ge=0, le=5),
):
    """Genera predicciones de actividad sísmica futura."""
    try:
        if not predictor.is_trained:
            return {
                "status": "error",
                "message": "El modelo no está entrenado. Use POST /api/train primero.",
            }

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)

        kwargs = {
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "min_magnitude": min_magnitude,
        }

        if region and region in REGIONS:
            r = REGIONS[region]
            kwargs.update({
                "min_latitude": r["min_lat"],
                "max_latitude": r["max_lat"],
                "min_longitude": r["min_lon"],
                "max_longitude": r["max_lon"],
            })

        data = await fetch_historical_earthquakes(**kwargs)
        df = geojson_to_dataframe(data)

        if df.empty:
            return {"status": "error", "message": "No hay datos suficientes para generar predicciones"}

        predictions = predictor.predict(df)

        # Filtrar solo predicciones significativas
        significant = [p for p in predictions if p["probability"] >= 0.1]

        return {
            "status": "success",
            "region": region or "global",
            "prediction_window": f"Próximos 30 días",
            "generated_at": datetime.utcnow().isoformat(),
            "model_accuracy": predictor.training_metrics.get("classifier_accuracy"),
            "total_zones_analyzed": len(predictions),
            "significant_predictions": len(significant),
            "predictions": significant[:50],  # Top 50
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/stats")
async def get_statistics(
    days_back: int = Query(default=30, ge=1, le=365),
    region: Optional[str] = Query(default=None),
):
    """Obtiene estadísticas de actividad sísmica."""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)

        kwargs = {
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "min_magnitude": 2.5,
        }

        if region and region in REGIONS:
            r = REGIONS[region]
            kwargs.update({
                "min_latitude": r["min_lat"],
                "max_latitude": r["max_lat"],
                "min_longitude": r["min_lon"],
                "max_longitude": r["max_lon"],
            })

        data = await fetch_historical_earthquakes(**kwargs)
        df = geojson_to_dataframe(data)

        if df.empty:
            return {"status": "success", "stats": {}}

        stats = {
            "total_events": len(df),
            "magnitude": {
                "mean": round(df["magnitude"].mean(), 2),
                "max": round(df["magnitude"].max(), 2),
                "min": round(df["magnitude"].min(), 2),
                "std": round(df["magnitude"].std(), 2),
            },
            "depth": {
                "mean": round(df["depth"].mean(), 2),
                "max": round(df["depth"].max(), 2),
                "min": round(df["depth"].min(), 2),
            },
            "by_magnitude_range": {
                "2.5-3.9": len(df[(df["magnitude"] >= 2.5) & (df["magnitude"] < 4.0)]),
                "4.0-4.9": len(df[(df["magnitude"] >= 4.0) & (df["magnitude"] < 5.0)]),
                "5.0-5.9": len(df[(df["magnitude"] >= 5.0) & (df["magnitude"] < 6.0)]),
                "6.0-6.9": len(df[(df["magnitude"] >= 6.0) & (df["magnitude"] < 7.0)]),
                "7.0+": len(df[df["magnitude"] >= 7.0]),
            },
            "tsunamis": int(df["tsunami"].sum()) if "tsunami" in df.columns else 0,
            "period": f"{days_back} días",
            "region": region or "global",
        }

        return {"status": "success", "stats": stats}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/model/status")
async def model_status():
    """Estado del modelo de predicción."""
    return {
        "is_trained": predictor.is_trained,
        "metrics": predictor.training_metrics if predictor.is_trained else None,
        "model_path": MODEL_PATH,
    }


@app.get("/api/regions")
async def get_regions():
    """Lista las regiones disponibles."""
    return {"regions": REGIONS}


@app.get("/api/feeds")
async def get_feeds():
    """Lista los feeds disponibles de USGS."""
    return {"feeds": list(FEEDS.keys())}


@app.get("/api/live/stream")
async def live_stream(request: Request):
    """Stream de Server-Sent Events con sismos en tiempo real."""
    queue = monitor.subscribe()

    async def event_generator():
        try:
            async for event in monitor.event_stream(queue):
                # Verificar si el cliente desconectó
                if await request.is_disconnected():
                    break
                yield event
        finally:
            monitor.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/live/status")
async def live_status():
    """Estado del monitor en vivo."""
    return {
        "is_running": monitor.is_running,
        "subscribers": len(monitor.subscribers),
        "last_check": monitor.last_check.isoformat() if monitor.last_check else None,
        "stats": monitor.stats,
    }
