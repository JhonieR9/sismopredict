"""Monitor en vivo de actividad sísmica con Server-Sent Events."""

import asyncio
import json
from datetime import datetime, timezone
from typing import AsyncGenerator
from app.data_fetcher import fetch_realtime_earthquakes, geojson_to_dataframe


class SeismicMonitor:
    """
    Monitorea la API de USGS periódicamente y detecta nuevos sismos.
    Mantiene un registro de IDs ya vistos para enviar solo eventos nuevos.
    """

    def __init__(self):
        self.seen_ids: set = set()
        self.subscribers: list[asyncio.Queue] = []
        self.is_running = False
        self.last_check: datetime | None = None
        self.stats = {
            "total_detected": 0,
            "checks_performed": 0,
            "last_significant": None,
        }

    async def start(self):
        """Inicia el monitoreo continuo."""
        if self.is_running:
            return
        self.is_running = True
        asyncio.create_task(self._monitor_loop())
        print("📡 Monitor sísmico en vivo iniciado")

    async def stop(self):
        """Detiene el monitoreo."""
        self.is_running = False
        print("📡 Monitor sísmico detenido")

    def subscribe(self) -> asyncio.Queue:
        """Registra un nuevo suscriptor para recibir eventos."""
        queue = asyncio.Queue()
        self.subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        """Elimina un suscriptor."""
        if queue in self.subscribers:
            self.subscribers.remove(queue)

    async def _broadcast(self, event: dict):
        """Envía un evento a todos los suscriptores."""
        dead_queues = []
        for queue in self.subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                dead_queues.append(queue)

        for q in dead_queues:
            self.subscribers.remove(q)

    async def _monitor_loop(self):
        """Loop principal de monitoreo."""
        # Primera carga: obtener sismos existentes para no notificar los antiguos
        await self._initial_load()

        while self.is_running:
            try:
                await self._check_for_new_earthquakes()
                self.stats["checks_performed"] += 1
                self.last_check = datetime.now(timezone.utc)
            except Exception as e:
                print(f"⚠️ Error en monitor: {e}")
                # Enviar evento de error a los suscriptores
                await self._broadcast({
                    "type": "error",
                    "message": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            # Esperar 30 segundos entre cada verificación
            await asyncio.sleep(30)

    async def _initial_load(self):
        """Carga inicial para registrar sismos existentes."""
        try:
            data = await fetch_realtime_earthquakes("hour_m1.0")
            df = geojson_to_dataframe(data)
            if not df.empty:
                self.seen_ids = set(df["id"].tolist())
                print(f"📡 Carga inicial: {len(self.seen_ids)} sismos registrados")

                # Enviar los sismos más recientes como contexto inicial
                await self._broadcast({
                    "type": "initial_load",
                    "count": len(df),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
        except Exception as e:
            print(f"⚠️ Error en carga inicial: {e}")

    async def _check_for_new_earthquakes(self):
        """Verifica si hay nuevos sismos desde la última comprobación."""
        # Consultar sismos de la última hora (incluye los más recientes)
        data = await fetch_realtime_earthquakes("hour_m1.0")
        df = geojson_to_dataframe(data)

        if df.empty:
            return

        current_ids = set(df["id"].tolist())
        new_ids = current_ids - self.seen_ids

        if new_ids:
            new_earthquakes = df[df["id"].isin(new_ids)]

            for _, eq in new_earthquakes.iterrows():
                event = {
                    "type": "new_earthquake",
                    "data": {
                        "id": eq.get("id", ""),
                        "magnitude": float(eq["magnitude"]) if eq["magnitude"] is not None else None,
                        "place": eq.get("place", "Ubicación desconocida"),
                        "time": str(eq.get("datetime", "")),
                        "latitude": float(eq["latitude"]) if eq["latitude"] is not None else None,
                        "longitude": float(eq["longitude"]) if eq["longitude"] is not None else None,
                        "depth": float(eq["depth"]) if eq["depth"] is not None else None,
                        "tsunami": int(eq.get("tsunami", 0)),
                        "sig": int(eq.get("sig", 0)),
                        "alert": eq.get("alert"),
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                # Clasificar severidad
                mag = eq.get("magnitude", 0) or 0
                if mag >= 7.0:
                    event["severity"] = "critical"
                elif mag >= 5.5:
                    event["severity"] = "high"
                elif mag >= 4.0:
                    event["severity"] = "medium"
                else:
                    event["severity"] = "low"

                await self._broadcast(event)
                self.stats["total_detected"] += 1

                if mag >= 4.5:
                    self.stats["last_significant"] = {
                        "magnitude": mag,
                        "place": eq.get("place", ""),
                        "time": str(eq.get("datetime", "")),
                    }

                print(f"🔔 NUEVO SISMO: M{mag:.1f} - {eq.get('place', 'Desconocido')}")

            # Actualizar IDs vistos
            self.seen_ids = current_ids

            # Enviar resumen si hay múltiples
            if len(new_ids) > 1:
                await self._broadcast({
                    "type": "batch_summary",
                    "count": len(new_ids),
                    "max_magnitude": float(new_earthquakes["magnitude"].max()),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

    async def event_stream(self, queue: asyncio.Queue) -> AsyncGenerator[str, None]:
        """Genera el stream de SSE para un cliente."""
        try:
            # Enviar evento de conexión
            yield self._format_sse({
                "type": "connected",
                "message": "Conectado al monitor sísmico en vivo",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "stats": self.stats,
            })

            while True:
                try:
                    # Esperar evento con timeout para mantener la conexión viva
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield self._format_sse(event)
                except asyncio.TimeoutError:
                    # Enviar keepalive (comentario SSE)
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass

    def _format_sse(self, data: dict) -> str:
        """Formatea un evento para SSE."""
        json_data = json.dumps(data, ensure_ascii=False)
        return f"data: {json_data}\n\n"


# Instancia global del monitor
monitor = SeismicMonitor()
