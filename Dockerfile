FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el proyecto
COPY . .

# Puerto (Railway y Render usan la variable PORT)
ENV PORT=8000
EXPOSE ${PORT}

# Comando de inicio
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
