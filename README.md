# 🌍 SismoPredict - Sistema de Predicción Sísmica con IA

Sistema profesional de monitoreo y predicción de sismos en tiempo real utilizando Machine Learning.

## Características

- **Monitoreo en tiempo real**: Datos sísmicos del USGS actualizados cada 5 minutos
- **Mapa interactivo**: Visualización global de actividad sísmica con Leaflet
- **Predicción con IA**: Modelo Random Forest + Gradient Boosting para estimar probabilidad de sismos futuros
- **Dashboard profesional**: Interfaz oscura con estadísticas, gráficas y alertas
- **Multi-región**: Soporte para México, Chile, Japón, California, Indonesia y global
- **API REST**: Endpoints completos para integración con otros sistemas

## Tecnologías

- **Backend**: Python, FastAPI, scikit-learn
- **Frontend**: HTML5, CSS3, JavaScript, Leaflet.js, Chart.js
- **ML**: Random Forest (clasificación), Gradient Boosting (regresión)
- **Datos**: USGS Earthquake API (datos en tiempo real e históricos)

## Instalación

```bash
# 1. Crear entorno virtual
python -m venv venv

# 2. Activar entorno virtual
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Ejecutar la aplicación
python run.py
```

La aplicación estará disponible en: **http://localhost:8000**

## Uso

### Dashboard
1. Abrir http://localhost:8000 en el navegador
2. Los sismos en tiempo real se cargan automáticamente
3. Usar los selectores para filtrar por región y periodo

### Entrenar el Modelo
1. Hacer clic en "Entrenar IA" en el dashboard
2. El sistema descargará 3 años de datos históricos del USGS
3. El modelo se entrenará y guardará automáticamente (~2-5 min)

### Generar Predicciones
1. Asegurarse de que el modelo esté entrenado (indicador verde)
2. Seleccionar la región deseada
3. Hacer clic en "Predecir"
4. Las predicciones aparecerán en el mapa y en el panel lateral

## API Endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/earthquakes/realtime` | Sismos en tiempo real |
| GET | `/api/earthquakes/historical` | Datos históricos |
| POST | `/api/train` | Entrenar modelo de IA |
| GET | `/api/predict` | Generar predicciones |
| GET | `/api/stats` | Estadísticas sísmicas |
| GET | `/api/model/status` | Estado del modelo |
| GET | `/api/regions` | Regiones disponibles |

## Sobre la Predicción

El modelo utiliza features sísmicas incluyendo:
- Frecuencia de eventos por zona
- Magnitud promedio y máxima histórica
- b-value (Ley de Gutenberg-Richter)
- Energía acumulada liberada
- Intervalos entre eventos
- Profundidad promedio

**Nota**: La predicción exacta de sismos es un problema abierto en sismología. Este sistema estima probabilidades basadas en patrones estadísticos históricos, no predice eventos individuales con certeza.

## Estructura del Proyecto

```
sismopredict/
├── app/
│   ├── __init__.py
│   ├── main.py          # API FastAPI
│   ├── config.py        # Configuración
│   ├── data_fetcher.py  # Obtención de datos USGS
│   ├── predictor.py     # Modelo de ML
│   └── models/          # Modelos guardados
├── templates/
│   └── dashboard.html   # Frontend
├── static/              # Archivos estáticos
├── requirements.txt
├── run.py               # Script de ejecución
└── README.md
```

## Licencia

MIT
