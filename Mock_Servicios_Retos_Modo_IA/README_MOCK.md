# Servicios simulados (mock) · Hackatón de Porvenir en Modo IA

Un solo archivo, sin instalar nada: `mock_server.py`. Requiere Python 3.8 o superior.

## Cómo se usa

```
python mock_server.py 01        # reto 01 en http://localhost:8080
python mock_server.py 05 9000   # reto 05 en otro puerto
```

| Reto | Comando | Simula |
|---|---|---|
| 01 Buzón judicial | `python mock_server.py 01` | Multifondos: afiliados, casos y asignación |
| 02 Detective de rezagos | `python mock_server.py 02` | Core de afiliados y bitácora de decisiones |
| 03 Gestor de bonos | `python mock_server.py 03` | Expedientes, tareas, entidad emisora y notificaciones |
| 04 Ahorro voluntario | `python mock_server.py 04` | Alternativas, validación de aportes, metas y panel |
| 05 Radicación | `python mock_server.py 05` | Requisitos, solicitudes, avance, beneficiarios y radicación |

Abra `http://localhost:8080/` para ver la lista de operaciones del reto con su descripción.

## Reglas del mock

- Lee los datos de `./data/<carpeta del reto>`. Deje `mock_server.py` junto a la carpeta `data`.
- Responde y recibe JSON. Acepta llamadas desde el navegador (CORS abierto).
- No entrega las columnas de respuesta esperada. Esas columnas siguen en los CSV para medir el prototipo.
- Guarda lo que el equipo crea en `mock_state_<reto>.json`. El estado sobrevive a un reinicio.
- `POST /_reset` borra el estado y deja el servicio como al inicio. Úselo antes de la demo.
- Errores con significado: 400 falta un campo, 404 no existe, 409 duplicado, 422 la regla de negocio no se cumple.

## Ejemplos

```
curl "http://localhost:8080/afiliados?documento=9000010004"
curl -X POST http://localhost:8080/casos -H "Content-Type: application/json" \
     -d '{"correo_id":"COR-001","radicado":"1100140030220260000100","categoria":"Tutela","validaciones":"OK"}'
```

## Lo que el mock no hace, a propósito

- No clasifica correos, no compara nombres parecidos y no valida documentos. Esa lógica es el reto.
- No se conecta a ningún sistema real. Todos los datos son sintéticos.

El equipo puede modificar o reemplazar el mock si lo justifica en su especificación.
