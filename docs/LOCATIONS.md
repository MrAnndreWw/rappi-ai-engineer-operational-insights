# Cobertura geográfica (20–50 direcciones)

Este documento debe acompañar a `config/locations.yaml` (no versionar datos personales si no aplica).

## Criterios sugeridos

- Mezcla de **tipos de zona**: residencial densa, comercial premium, comercial media, periferia, corredor turístico, etc.
- **Ciudades o clusters** relevantes para operación en México (ej. CDMX, GDL, MTY) según alcance de la prueba.
- Cada fila incluye: `id` estable, etiqueta legible, dirección o coordenadas, `zone_type`, y **notas** que justifiquen la elección.

## Plantilla

Duplica `config/locations.template.yaml` → `config/locations.yaml` y completa la lista. Añade aquí un resumen ejecutivo (tabla o bullet points) que referencie los `id` usados en los datos.

## Privacidad

Evita incluir datos personales innecesarios. Si usas direcciones reales, anonimiza en el repo público si la evaluación lo permite.
