# Competitive Intelligence — Delivery México

Sistema base para **Competitive Intelligence** orientado a plataformas de delivery en México (**Rappi**, **Uber Eats**, **DiDi Food**). El repositorio está organizado para una prueba técnica de **AI Engineer**: scraping reproducible, datos normalizados, análisis e informe, sin sobrecargar la primera iteración con lógica de negocio completa.

## Overview del caso

Se busca un pipeline automatizado que recolecte señales comparables (precios, fees, tiempos, promociones, disponibilidad, etc.) en un conjunto **representativo de 20–50 ubicaciones**, usando **productos de referencia** alineados entre apps, y que produzca **insights accionables** para Strategy, Pricing y Operations.

## Objetivos

- Scrapers **independientes por plataforma** con contrato común.
- Capa de **extracción** (parsers compartidos) y **transformación** hacia un esquema canónico.
- **Pipelines** ejecutables por CLI o scripts.
- **Análisis** y **reporting** separados del scraping.
- Estructura **escalable** a más competidores o verticales.

## Arquitectura del proyecto

```
config/               → YAML de proyecto, ubicaciones, catálogo de referencia
src/competitive_intel/
  scrapers/           → Un paquete por plataforma (rappi, uber_eats, didi_food)
  extract/            → Parsing reutilizable de respuestas crudas
  transform/          → Estandarización → modelos canónicos
  models/             → Esquemas (Pydantic)
  pipelines/          → Orquestación scrape → raw → processed
  analysis/           → Agregaciones e insights
  reporting/          → Figuras + ensamblado del informe
  utils/              → Rutas, logging
scripts/              → Atajos para scrape y reporte
tests/
data/raw|processed|external/   → Datos (crudo / intermedio / externo)
outputs/reports|figures|exports/
docs/                 → Justificación geográfica, notas de arquitectura
```

Detalle ampliado: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Estructura de carpetas

| Ruta | Propósito |
|------|-----------|
| `config/default.yaml` | Plataformas, métricas objetivo, timeouts, delays |
| `config/locations.template.yaml` / `locations.example.yaml` | Plantilla y ejemplo de ubicaciones |
| `config/reference_products.yaml` | Big Mac/Whopper, combo, nuggets, bebidas, pañales, etc. |
| `src/competitive_intel/scrapers/*` | Implementación por competidor |
| `data/raw` | Respuestas o extracts crudos (no subir datos sensibles) |
| `data/processed` | JSONL/CSV normalizado listo para análisis |
| `outputs/` | Exports finales, figuras, borradores de informe |

## Instalación

Requisitos: **Python 3.11+**.

```bash
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
pip install -U pip
pip install -r requirements.txt
pip install -e .
playwright install chromium
```

La instalación editable (`-e .`) registra el paquete `competitive_intel` desde `src/`. **Playwright** necesita el binario del navegador (`playwright install chromium`) para el scraping.

## Configuración

1. Copia `.env.example` a `.env` y ajusta solo lo necesario.
2. Crea `config/locations.yaml` (puedes partir de `config/locations.example.yaml`) con `id`, `address_line` (o `label`) y metadatos de zona.
3. Documenta criterio y justificación en [docs/LOCATIONS.md](docs/LOCATIONS.md).

## Cómo ejecutar el scraper

CLI (módulo principal):

```bash
python -m competitive_intel scrape --dry-run
python -m competitive_intel scrape
python -m competitive_intel scrape --platform uber_eats --headed
```

Script de ejemplo:

```bash
python scripts/run_scrape.py --dry-run
python scripts/run_scrape.py
python scripts/run_scrape.py --platform rappi --headed
```

El pipeline abre **Chromium** (Playwright), recorre las plataformas habilitadas en `config/default.yaml`, aplica **delays con jitter** entre pasos y ubicaciones, y escribe **`data/raw/scrape_<timestamp>.jsonl`** más un `*_meta.json`. Los selectores pueden requerir ajuste si las UIs cambian; revisa `scrapers/flows.py`.

## Cómo generar el reporte

Con datos normalizados en `data/processed/offers_normalized.jsonl` (o otro archivo):

```bash
python -m competitive_intel report
python scripts/run_report.py --input path/al/archivo.jsonl
```

Sin entrada, se genera un stub en `outputs/reports/report_stub.json`. La lógica de insights y visualizaciones se completará cuando existan columnas reales.

## Outputs esperados

- **Scraping**: archivos crudos bajo `data/raw/`; export reproducible JSONL/CSV en `data/processed/` y/o `outputs/exports/`.
- **Informe**: al menos **5 insights** accionables, comparativos (precios, tiempos, fees, promos, geografía), **≥3 visualizaciones** en `outputs/figures/`.
- **README** (este archivo): setup, ejecución, limitaciones, ética.

## Limitaciones conocidas

- Los scrapers son **placeholders** hasta definir método (API oficial, export interno, automatización controlada, etc.).
- La comparabilidad depende de **matching** de productos y de la homogeneidad de la oferta por zona.
- Las plataformas cambian UI y estructuras con frecuencia: hace falta versionar el “contrato” de extracción y pruebas de regresión.

## Consideraciones éticas y técnicas

- Respetar **Términos de uso**, políticas del sitio y **marco legal** aplicable en México.
- Preferir **fuentes autorizadas**, **rate limiting**, minimizar carga en infraestructura ajena y **no recolectar datos personales** innecesarios.
- Tratar outputs como **datos sensibles comerciales**; no publicar credenciales ni dumps completos sin permiso.
- Transparencia en el informe sobre **hipótesis**, **sesgos geográficos** y **calidad de datos**.

## Próximos pasos

1. Implementar recolección por plataforma y persistencia cruda versionada (sin secretos).
2. Completar `transform/canonical.py` y export a `offers_normalized.jsonl`.
3. Añadir pruebas de integración con fixtures.
4. Implementar `analysis/insights.py` y gráficos en `reporting/` (matplotlib/plotly + plantilla en `reporting/templates/`).
5. Redactar informe final enlazando figuras y metodología.

## Licencia y uso

Uso previsto: **prueba técnica / evaluación**. Ajusta autor y licencia según políticas de Rappi o del proceso de selección.
