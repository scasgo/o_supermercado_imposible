# O supermercado imposible — guía rápida de ejecución

## Requisitos
- Python 3.12 recomendado.
- Un proyecto Supabase con `sql/schema.sql` ejecutado.
- `.streamlit/secrets.toml` creado a partir de `.streamlit/secrets.toml.example`.

## Arranque local
Desde la carpeta raíz del proyecto:

```bash
python -m venv .venv
```

Activa el entorno virtual.

Windows PowerShell:
```powershell
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:
```bash
source .venv/bin/activate
```

Instala dependencias:
```bash
python -m pip install -r requirements-dev.txt
```

Ejecuta pruebas:
```bash
python -m pytest -q
```

Arranca Streamlit:
```bash
python -m streamlit run streamlit_app.py
```

Participante: `http://localhost:8501/`

Dashboard: `http://localhost:8501/?view=dashboard`

## Antes del evento
En `.streamlit/secrets.toml` y en los Secrets de Streamlit Community Cloud:

```toml
APP_MODE = "production"
DASHBOARD_DEMO = false
KIOSK_MODE = false
```

Comprueba que el dashboard ya no muestra la banda amarilla `DEMO`.

## QR
Con la URL pública definitiva:

```bash
python scripts/generate_qr.py https://TU-APP.streamlit.app/
```

Se crean `assets/qr_app.png` y `assets/qr_app.svg`.
