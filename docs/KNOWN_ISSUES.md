# Problemas conocidos y cómo se abordaron

Historial de incidencias frecuentes durante el desarrollo del scraper y el pipeline de comparación, con causa y mitigación aplicada en el código o en la configuración.

---

## 1. Muro anti-bot / obligación de iniciar sesión (Rappi)

**Síntoma:** Rappi muestra el modal «Confirma tu identidad» y pide registrarse o iniciar sesión para seguir navegando.

**Causa:** Tráfico automatizado intensivo o sesión anónima; la plataforma trata de frenar bots o sesiones sin cuenta.

**Solución aplicada:** Playwright carga y guarda el estado de sesión en `config/auth.json` (`storage_state`). Flujo recomendado:

1. Ejecutar con `--headed` la primera vez (o cuando vuelva el muro).
2. Completar login manual (teléfono / OTP).
3. Al terminar el run, el pipeline persiste la sesión en `config/auth.json`.
4. Runs posteriores (incluso headless) reutilizan ese archivo.

**Notas:** `config/auth.json` está en `.gitignore` y no debe subirse al repositorio; usar `config/auth.json.example` como referencia. Si el archivo filtró en git, rotar sesión y credenciales.

---

## 2. HTTP 429 Too Many Requests

**Síntoma:** Respuestas 429 o bloqueos intermitentes al recorrer muchas zonas, cadenas y scrolls de menú.

**Causa:** Demasiadas peticiones HTTP/XHR en poco tiempo (misma IP, patrón repetitivo).

**Solución aplicada:** Pausas configurables en `config/default.yaml`:

- `delay_seconds`, `delay_jitter_seconds`
- `between_locations_seconds`, `between_platforms_seconds`
- `scraping.rappi.between_chains_seconds`
- `scraping.uber_eats.between_chains_seconds` (antes Uber solo tenía un delay corto entre cadenas)

Comentario en YAML: si vuelve el 429, subir esos valores o partir el run (`--max-locations`, una plataforma por corrida).

---

## 3. Menú Rappi truncado (pocos productos vs Uber)

**Síntoma:** Solo aparecían ~10 ítems en Rappi mientras Uber listaba muchos más.

**Causa:** Límite fijo en la extracción y/o falta de scroll hasta estabilizar el DOM.

**Solución aplicada:** `scraping.rappi.menu_items_limit` puede ser `null` o `0` (sin límite práctico); el flujo hace scroll hasta que el conteo de tarjetas se estabiliza (con tope de seguridad interno en JS) y deduplica resultados.

---

## 4. Logs excesivos en consola

**Síntoma:** Demasiadas líneas `INFO` (timings por cadena, Playwright, pausas, sesión, etc.).

**Causa:** Todo el detalle operativo estaba a nivel `INFO`.

**Solución aplicada:** Por defecto solo quedan mensajes esenciales (progreso por ubicación, resumen del run, ruta del JSON de comparación, `WARNING`). El detalle (timings, carga de sesión, etc.) pasa a `DEBUG` y se activa con `-v` / `--verbose`.

---

## 5. Tarifa de envío Rappi en `null` en exports

**Síntoma:** En JSON de comparación, `delivery_comparison.rappi.fee_mxn` / `fee_raw` iban vacíos aunque en la UI aparecía **Envío → Gratis** (o precio) junto al `chakra-skeleton`.

**Causa principal corregida:** En `_rappi_extract_store_operational_meta` el JS buscaba la etiqueta literal **`Env?o`** (carácter incorrecto) en lugar de **`Envío`**, así que `rowValueAfterLabel` nunca coincidía con el `<span>Envío</span>`. El regex de respaldo usaba `Env?o` (en regex el `?` hacía opcional la `v`), tampoco válido.

**Solución aplicada:** Etiquetas con escapes Unicode en JS (`Env\u00edo`, `Calificaci\u00f3n`), misma lógica de fila + `.chakra-skeleton` para leer **Gratis** o el monto. `parse_delivery_fee_mxn` ya mapeaba **Gratis** → `0.0` cuando `fee_raw` llega informado.

**Si sigue en null:** valor aún no hidratado al momento del `evaluate` (skeleton vacío); probar un `wait_for_timeout` extra o esperar texto en el skeleton.

---

## 6. Celdas de comparación vacías o muy desbalanceadas

**Síntoma:** Por zona/cadena, `rappi_total: 0` o muchos `uber_only` sin matches (ej. fallo de dirección, tienda no cargada, 429).

**Causa:** Fallo puntual del scrape (UI, cobertura, rate limit), no del módulo de comparación.

**Mitigación:** Revisar el `scrape_*.jsonl` (`status`, `error`, `menu_error`), reintentar esa ubicación, subir delays ante 429, comprobar `auth.json` y selectores.

---

## 7. Archivo `locations.yaml` ausente

**Síntoma:** `No hay ubicaciones: crea config/locations.yaml`.

**Causa:** El archivo no existe o quedó vacío; el pipeline cae en `locations.template.yaml` (`locations: []`).

**Solución:** Copiar desde `config/locations.example.yaml` o la plantilla y definir al menos `id`, `address_line` (o `label`).

---

## 8. Código muerto y paquetes stub no usados

**Síntoma:** Carpetas `scrapers/rappi`, `uber_eats`, `didi_food` con clases placeholder que no llamaba el pipeline.

**Solución aplicada:** Eliminados stubs; el scraping real vive en `scrapers/flows.py` y `FLOW_REGISTRY`. Documentación actualizada en `README.md` y `docs/ARCHITECTURE.md`.

---

*Última revisión: alineado con el estado del repo tras limpieza de código, throttling y ajustes de logging.*
