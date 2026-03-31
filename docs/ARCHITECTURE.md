# Arquitectura (resumen)

## Flujo de datos

1. **Configuración** (`config/*.yaml`, `.env`, `config/auth.json` opcional para Rappi): plataformas activas, ubicaciones, productos de referencia, límites de cortesía.
2. **Scrape** (`scrapers/flows.py`): un módulo por responsabilidad; `FLOW_REGISTRY` mapea `rappi` / `uber_eats` / `didi_food` a funciones que devuelven filas JSONL por ubicación (Playwright).
3. **Extracción**: hoy vive junto a los flujos en `flows.py` (selectores, scroll, `page.evaluate`); si crece, se puede partir a `extract/` sin cambiar el contrato del JSONL.
4. **Transformación** (`transform/`): mapeo a esquemas canónicos (`models/schemas.py`).
5. **Persistencia**: crudo en `data/raw/`, normalizado en `data/processed/`, entregables en `outputs/`.
6. **Análisis** (`analysis/`): agregaciones, rankings, comparativos geográficos.
7. **Reporting** (`reporting/`): figuras en `outputs/figures/`, narrativa en `outputs/reports/` (Markdown/HTML/PDF según implementación).

## Extensión

- Nuevo competidor: nueva función en `scrapers/flows.py`, entrada en `FLOW_REGISTRY`, plataforma en `config/default.yaml`, y ampliar `PlatformId` en `models/schemas.py` si aplica.
- Nuevas verticales: nuevos `reference_product_id` y reglas de matching en transformación.
