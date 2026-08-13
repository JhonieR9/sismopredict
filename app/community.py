"""Sistema de reportes comunitarios - 'Yo lo sentí'."""

import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Optional
from dataclasses import dataclass, asdict


@dataclass
class FeltReport:
    """Reporte de un usuario que sintió un sismo."""
    id: str
    latitude: float
    longitude: float
    intensity: int  # 1-10 (Mercalli simplificado)
    timestamp: str
    description: str = ""
    city: str = ""
    country: str = ""
    duration_seconds: int = 0
    indoors: bool = True
    floor: int = 0


class CommunityReports:
    """
    Gestiona reportes de la comunidad y detecta sismos basándose en
    clusters de reportes simultáneos.
    """

    def __init__(self):
        self.reports: list[dict] = []
        self.detected_events: list[dict] = []
        self.subscribers: list[asyncio.Queue] = []
        self._report_counter = 0

    def subscribe(self) -> asyncio.Queue:
        queue = asyncio.Queue(maxsize=50)
        self.subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        if queue in self.subscribers:
            self.subscribers.remove(queue)

    async def _broadcast(self, event: dict):
        dead = []
        for q in self.subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self.subscribers.remove(q)

    async def add_report(self, report_data: dict) -> dict:
        """Agrega un nuevo reporte 'Yo lo sentí'."""
        self._report_counter += 1

        report = {
            "id": f"report_{self._report_counter}_{int(datetime.now(timezone.utc).timestamp())}",
            "latitude": report_data["latitude"],
            "longitude": report_data["longitude"],
            "intensity": min(10, max(1, report_data.get("intensity", 3))),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "description": report_data.get("description", ""),
            "city": report_data.get("city", ""),
            "country": report_data.get("country", "Colombia"),
            "duration_seconds": report_data.get("duration_seconds", 0),
            "indoors": report_data.get("indoors", True),
            "floor": report_data.get("floor", 0),
        }

        self.reports.append(report)

        # Mantener solo últimos 500 reportes
        if len(self.reports) > 500:
            self.reports = self.reports[-500:]

        # Verificar si hay un cluster de reportes (posible sismo no registrado)
        cluster = self._detect_cluster()
        if cluster:
            self.detected_events.append(cluster)
            await self._broadcast({
                "type": "community_detection",
                "event": cluster,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        # Broadcast el reporte individual
        await self._broadcast({
            "type": "new_report",
            "report": report,
            "total_reports_last_hour": self._count_recent_reports(60),
        })

        return report

    def _detect_cluster(self) -> Optional[dict]:
        """
        Detecta un posible sismo basándose en múltiples reportes
        cercanos en tiempo y espacio (últimos 5 minutos).
        """
        now = datetime.now(timezone.utc)
        five_min_ago = now - timedelta(minutes=5)

        # Reportes de los últimos 5 minutos
        recent = [
            r for r in self.reports
            if datetime.fromisoformat(r["timestamp"]) > five_min_ago
        ]

        if len(recent) < 3:  # Necesitamos al menos 3 reportes
            return None

        # Calcular centro del cluster
        lats = [r["latitude"] for r in recent]
        lons = [r["longitude"] for r in recent]
        intensities = [r["intensity"] for r in recent]

        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)
        avg_intensity = sum(intensities) / len(intensities)
        max_intensity = max(intensities)

        # Estimar magnitud basada en intensidad y número de reportes
        estimated_mag = self._estimate_magnitude(avg_intensity, len(recent))

        # Verificar que no es un evento ya detectado (evitar duplicados)
        for event in self.detected_events[-10:]:
            event_time = datetime.fromisoformat(event["timestamp"])
            if (now - event_time) < timedelta(minutes=10):
                # Ya hay un evento reciente, no crear otro
                return None

        return {
            "id": f"community_{int(now.timestamp())}",
            "type": "community_detected",
            "latitude": round(center_lat, 4),
            "longitude": round(center_lon, 4),
            "estimated_magnitude": round(estimated_mag, 1),
            "avg_intensity": round(avg_intensity, 1),
            "max_intensity": max_intensity,
            "report_count": len(recent),
            "timestamp": now.isoformat(),
            "confidence": min(0.95, len(recent) * 0.15),  # Más reportes = más confianza
            "cities": list(set(r["city"] for r in recent if r["city"])),
            "source": "community",
        }

    def _estimate_magnitude(self, avg_intensity: int, report_count: int) -> float:
        """Estima magnitud a partir de intensidad Mercalli y densidad de reportes."""
        # Conversión aproximada Mercalli -> Magnitud
        intensity_to_mag = {
            1: 2.0, 2: 2.5, 3: 3.0, 4: 3.5, 5: 4.0,
            6: 5.0, 7: 5.5, 8: 6.0, 9: 6.5, 10: 7.0,
        }
        base_mag = intensity_to_mag.get(round(avg_intensity), 3.0)

        # Ajustar por número de reportes (más reportes sugiere mayor magnitud)
        if report_count > 20:
            base_mag += 0.5
        elif report_count > 10:
            base_mag += 0.3

        return base_mag

    def _count_recent_reports(self, minutes: int) -> int:
        """Cuenta reportes en los últimos N minutos."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        return sum(
            1 for r in self.reports
            if datetime.fromisoformat(r["timestamp"]) > cutoff
        )

    def get_recent_reports(self, hours: int = 24) -> list[dict]:
        """Obtiene reportes recientes."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return [
            r for r in self.reports
            if datetime.fromisoformat(r["timestamp"]) > cutoff
        ]

    def get_stats(self) -> dict:
        """Estadísticas de la comunidad."""
        return {
            "total_reports": len(self.reports),
            "reports_last_hour": self._count_recent_reports(60),
            "reports_last_24h": self._count_recent_reports(1440),
            "detected_events": len(self.detected_events),
            "active_reporters": len(set(
                f"{r['latitude']:.2f},{r['longitude']:.2f}"
                for r in self.get_recent_reports(1)
            )),
        }

    def get_heatmap_data(self) -> list[dict]:
        """Datos para mapa de calor de reportes."""
        recent = self.get_recent_reports(24)
        return [
            {"lat": r["latitude"], "lon": r["longitude"], "intensity": r["intensity"]}
            for r in recent
        ]


# Instancia global
community = CommunityReports()
