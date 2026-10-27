# Cómo cargar el contenido real de Electorry (tarea S2-R3)

1. Abre `servicios.csv` y `productos.csv` con Excel (o Google Sheets). Cada fila es un servicio o producto.
   Las filas que empiezan con `#` se ignoran (son ejemplos: bórralas o déjalas).
2. Guarda como **CSV** (en Excel: *Guardar como → CSV UTF-8*). Sirven coma o punto y coma.
3. Fotos de productos: copia los archivos JPG/PNG (máx. 2 MB) en `imagenes/` y escribe el nombre exacto en la columna `imagen`.
4. Valida sin guardar:  `python manage.py importar_contenido contenido --simular`
5. Si todo está bien, guarda:  `python manage.py importar_contenido contenido`

El comando es **repetible**: si el nombre ya existe, actualiza la fila en vez de duplicarla. Si hay un error, **no guarda nada**
y lista cada problema con su número de línea.

## Columnas

| Archivo | Columna | Obligatoria | Detalle |
|---|---|:-:|---|
| servicios | categoria | Sí | Se crea sola si no existe (ej.: Instalaciones, Mantención) |
| servicios | nombre | Sí | Máx. 150 caracteres |
| servicios | resumen | Sí | Frase corta que aparece en el catálogo (máx. 250) |
| servicios | descripcion | Sí | Detalle completo: qué incluye y qué no |
| servicios | disponible | No | Sí / No. Vacío = Sí |
| productos | categoria | Sí | Se crea sola |
| productos | nombre | Sí | Máx. 150 caracteres |
| productos | descripcion | No | Texto del producto |
| productos | precio | Sí | Pesos chilenos **con IVA incluido**, número entero. Acepta `$12.990` o `12990` |
| productos | activo | No | Sí / No. Vacío = Sí |
| productos | imagen | No | Nombre del archivo dentro de `imagenes/`. Solo se carga si el producto aún no tiene foto |

Los **datos de contacto, redes sociales y textos institucionales** no se cargan con este comando: hoy se configuran por variables
de entorno y pasarán a ser editables desde el panel en la tarea S3-J1. Recopílalos igualmente (ver la guía de la reunión).
