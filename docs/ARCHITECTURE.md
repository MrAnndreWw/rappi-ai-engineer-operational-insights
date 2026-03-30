# Arquitectura (resumen)

## Flujo de datos

1. **Configuración** (`config/*.yaml`, `.env`): plataformas activas, ubicaciones, productos de referencia, límites de cortesía.
2. **Scrape** (`scrapers/<platform>/`): cada competidor encapsula cómo obtiene filas semi-estructuradas por ubicación.
3. **Extracción** (`extract/`): parsers y helpers compartidos (JSON/HTML) desacoplados de la orquestación.
4. **Transformación** (`transform/`): mapeo a esquemas canónicos (`models/schemas.py`).
5. **Persistencia**: crudo en `data/raw/`, normalizado en `data/processed/`, entregables en `outputs/`.
6. **Análisis** (`analysis/`): agregaciones, rankings, comparativos geográficos.
7. **Reporting** (`reporting/`): figuras en `outputs/figures/`, narrativa en `outputs/reports/` (Markdown/HTML/PDF según implementación).

## Extensión

- Nuevo competidor: carpeta bajo `scrapers/`, registro en `config/default.yaml`, ampliar `PlatformId` en `models/schemas.py`.
- Nuevas verticales: nuevos `reference_product_id` y reglas de matching en transformación.
