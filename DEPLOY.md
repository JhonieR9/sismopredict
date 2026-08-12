# 🚀 Cómo Compartir SismoPredict con Otras Personas

Tienes 3 opciones para poner la app en internet (todas gratuitas):

---

## Opción 1: Railway (Recomendada - Más fácil)

**Gratis**: 500 horas/mes + $5 USD de crédito mensual (suficiente para correr 24/7)

### Pasos:

1. **Crear cuenta** en https://railway.app (puedes usar tu cuenta de GitHub)

2. **Subir el proyecto a GitHub**:
   ```bash
   cd C:\Users\Usuario\Desktop\prueba
   git init
   git add .
   git commit -m "SismoPredict v1.0"
   ```
   Luego crea un repositorio en https://github.com/new y sube:
   ```bash
   git remote add origin https://github.com/TU_USUARIO/sismopredict.git
   git branch -M main
   git push -u origin main
   ```

3. **Desplegar en Railway**:
   - Ir a https://railway.app/new
   - Clic en "Deploy from GitHub repo"
   - Seleccionar tu repositorio "sismopredict"
   - Railway detectará automáticamente el Dockerfile
   - Esperar 2-3 minutos a que se construya
   - Ir a Settings → Networking → "Generate Domain"
   - ¡Listo! Tendrás un link como: `sismopredict-production.up.railway.app`

4. **Compartir el link** con quien quieras 🎉

---

## Opción 2: Render (Fácil, sin tarjeta)

**Gratis**: Plan Free (se apaga después de 15 min de inactividad, se reactiva al visitar)

### Pasos:

1. **Crear cuenta** en https://render.com (usa GitHub)

2. **Subir a GitHub** (mismo paso que arriba)

3. **Desplegar en Render**:
   - Ir a https://dashboard.render.com/new/web-service
   - Conectar tu repositorio de GitHub
   - Configurar:
     - **Name**: sismopredict
     - **Runtime**: Python 3
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Clic en "Create Web Service"
   - Esperar 3-5 minutos

4. **Tu link**: `sismopredict.onrender.com`

---

## Opción 3: Fly.io (Más potente)

**Gratis**: 3 VMs compartidas + 160GB de transferencia/mes

### Pasos:

1. **Instalar Fly CLI**:
   - Descargar de https://fly.io/docs/hands-on/install-flyctl/
   - Windows: `powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"`

2. **Login y desplegar**:
   ```bash
   cd C:\Users\Usuario\Desktop\prueba
   flyctl auth signup
   flyctl launch
   flyctl deploy
   ```

3. **Tu link**: `sismopredict.fly.dev`

---

## 📱 Compartir por WhatsApp/Telegram

Una vez desplegado, simplemente envía el link:

```
🌍 SismoPredict - Monitoreo de sismos en tiempo real con IA
Revisa la actividad sísmica desde tu celular:
👉 https://tu-app.railway.app
```

---

## Resumen Rápido (Lo más rápido posible)

```bash
# 1. Instalar Git si no lo tienes
# 2. Desde tu proyecto:
git init
git add .
git commit -m "SismoPredict v1.0"

# 3. Crear repo en GitHub y subir
git remote add origin https://github.com/TU_USUARIO/sismopredict.git
git push -u origin main

# 4. Ir a railway.app → New Project → Deploy from GitHub → Seleccionar repo
# 5. Esperar 2 min → Generate Domain → Compartir link
```

**Tiempo total**: ~10 minutos desde cero.
