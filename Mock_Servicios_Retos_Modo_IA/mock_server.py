#!/usr/bin/env python3
"""Servicios simulados (mock) de la Hackatón de Porvenir en Modo IA.

Uso:   python mock_server.py <reto> [puerto]      Ej.: python mock_server.py 01
Retos: 01 Buzón judicial · 02 Rezagos · 03 Bonos · 04 Ahorro voluntario · 05 Radicación
Sin dependencias: solo Python 3.8 o superior. Datos 100 % sintéticos, leídos de ./data.
El estado se guarda en mock_state_<reto>.json y sobrevive a un reinicio.
"""
import csv, json, os, re, sys, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

RETO = sys.argv[1] if len(sys.argv) > 1 else ""
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
BASE = os.path.dirname(os.path.abspath(__file__))
DIRS = {"01": "01_Buzon_Judicial", "02": "02_Rezagos", "03": "03_Bonos", "04": "04_Ahorro_Voluntario", "05": "05_Radicacion"}
if RETO not in DIRS:
    sys.exit(__doc__)
DATA = os.path.join(BASE, "data", DIRS[RETO])
STATE_FILE = os.path.join(BASE, f"mock_state_{RETO}.json")


def load(name):
    """Lee un CSV y oculta las columnas de respuesta esperada."""
    with open(os.path.join(DATA, name), encoding="utf-8-sig") as f:
        return [{k: v for k, v in row.items() if "esperad" not in k and k != "tipo_prueba"} for row in csv.DictReader(f)]


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


STATE = {}
if os.path.exists(STATE_FILE):
    STATE = json.load(open(STATE_FILE, encoding="utf-8"))


def save():
    json.dump(STATE, open(STATE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def col(name):
    return STATE.setdefault(name, [])


def nid(prefix, name):
    return f"{prefix}-{len(col(name)) + 1:04d}"


class Err(Exception):
    def __init__(self, code, msg, extra=None):
        self.code, self.msg, self.extra = code, msg, extra or {}


def need(body, *fields):
    miss = [f for f in fields if body.get(f) in (None, "")]
    if miss:
        raise Err(400, "Faltan campos obligatorios", {"campos": miss})


def find(rows, key, val, what):
    for r in rows:
        if r.get(key) == val:
            return r
    raise Err(404, f"{what} no existe", {key: val})


def filt(rows, q, fields):
    out = rows
    for f, param in fields.items():
        if param in q:
            v = q[param][0].strip().lower()
            out = [r for r in out if v in r[f].lower()] if "nombre" in f else [r for r in out if r[f] == q[param][0].strip()]
    return out


ROUTES = []


def route(method, pattern, desc):
    def deco(fn):
        ROUTES.append((method, re.compile("^" + re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", pattern) + "$"), pattern, desc, fn))
        return fn
    return deco


# ───────────────────────── Reto 01 · Buzón judicial (Multifondos simulado)
if RETO == "01":
    AFI = load("afiliados_core_mock.csv")
    COLAS = json.load(open(os.path.join(DATA, "catalogo_colas_mock.json"), encoding="utf-8"))["categoria_a_cola"]

    @route("GET", "/afiliados", "Consulta la maestra. Filtros: ?documento= (exacto) y ?nombre= (contiene)")
    def _(q, b, **k): return filt(AFI, q, {"documento_ficticio": "documento", "nombre": "nombre"})

    @route("GET", "/colas", "Cola de gestión por categoría")
    def _(q, b, **k): return COLAS

    @route("POST", "/casos", "Crea el caso solo si validaciones = OK. Rechaza un radicado ya registrado")
    def _(q, b, **k):
        need(b, "correo_id", "radicado", "categoria", "validaciones")
        if b["validaciones"] != "OK":
            raise Err(422, "El caso no se crea: las validaciones no están en OK. Envíelo a revisión humana.")
        if b["categoria"] not in COLAS:
            raise Err(422, "Categoría desconocida", {"categorias": list(COLAS)})
        for c in col("casos"):
            if c["radicado"] == b["radicado"]:
                raise Err(409, "Ya existe un caso con ese radicado: posible duplicado", {"caso_existente": c["caso_id"]})
        c = {"caso_id": nid("MF", "casos"), **b, "cola": b.get("cola") or COLAS[b["categoria"]], "responsable": b.get("responsable"), "estado": "CREADO", "creado": now()}
        col("casos").append(c); return 201, c

    @route("GET", "/casos", "Lista los casos creados")
    def _(q, b, **k): return col("casos")

    @route("GET", "/casos/{id}", "Retorna estado y asignación")
    def _(q, b, id): return find(col("casos"), "caso_id", id, "El caso")

    @route("PUT", "/casos/{id}/asignacion", "Asigna cola y responsable")
    def _(q, b, id):
        need(b, "responsable"); c = find(col("casos"), "caso_id", id, "El caso")
        c.update(responsable=b["responsable"], cola=b.get("cola", c["cola"]), estado="ASIGNADO", asignado=now()); return c

# ───────────────────────── Reto 02 · Rezagos (core de afiliados y bitácora)
if RETO == "02":
    AFI = load("maestra_afiliados.csv")

    @route("GET", "/afiliados", "Consulta la maestra. Filtros: ?documento= (exacto) y ?nombre= (contiene). El matching aproximado lo hace el equipo")
    def _(q, b, **k): return filt(AFI, q, {"documento_core": "documento", "nombre_core": "nombre"})

    @route("POST", "/resoluciones", "Registra la decisión sobre un pago en la bitácora. No acredita recursos")
    def _(q, b, **k):
        need(b, "pago_id", "decision", "usuario", "motivo")
        if b["decision"] not in ("APROBADO", "RECHAZADO", "SOLICITAR_SOPORTE"):
            raise Err(422, "Decisión no válida", {"decisiones": ["APROBADO", "RECHAZADO", "SOLICITAR_SOPORTE"]})
        if b["decision"] == "APROBADO":
            need(b, "afiliado_id"); find(AFI, "afiliado_id", b["afiliado_id"], "El afiliado")
        r = {"resolucion_id": nid("RES", "resoluciones"), **b, "fecha": now()}
        col("resoluciones").append(r); return 201, r

    @route("GET", "/resoluciones", "Consulta la bitácora. Filtro: ?pago_id=")
    def _(q, b, **k): return [r for r in col("resoluciones") if "pago_id" not in q or r["pago_id"] == q["pago_id"][0]]

# ───────────────────────── Reto 03 · Bonos pensionales
if RETO == "03":
    EXP, ETA, DOCS = load("expedientes_bonos.csv"), load("catalogo_etapas.csv"), load("catalogo_documentos.csv")

    @route("GET", "/expedientes", "Lista los expedientes")
    def _(q, b, **k): return EXP

    @route("GET", "/expedientes/{id}", "Retorna un expediente y su etapa")
    def _(q, b, id): return find(EXP, "caso_id", id, "El expediente")

    @route("GET", "/etapas", "Matriz de etapas")
    def _(q, b, **k): return ETA

    @route("GET", "/documentos", "Catálogo de documentos")
    def _(q, b, **k): return DOCS

    @route("POST", "/expedientes/{id}/tareas", "Crea una tarea con responsable")
    def _(q, b, id):
        find(EXP, "caso_id", id, "El expediente"); need(b, "descripcion", "responsable", "actor")
        if b["actor"] not in ("CLIENTE", "PORVENIR", "TERCERO"):
            raise Err(422, "Actor no válido", {"actores": ["CLIENTE", "PORVENIR", "TERCERO"]})
        t = {"tarea_id": nid("TAR", "tareas"), "caso_id": id, **b, "estado": "PENDIENTE", "creada": now()}
        col("tareas").append(t); return 201, t

    @route("GET", "/expedientes/{id}/tareas", "Lista las tareas de un expediente")
    def _(q, b, id): return [t for t in col("tareas") if t["caso_id"] == id]

    @route("GET", "/fuente-externa/{id}/estado", "Respuesta simulada de la entidad emisora. Nunca trae fecha de pago")
    def _(q, b, id):
        e = find(EXP, "caso_id", id, "El expediente")
        return {"caso_id": id, "estado_fuente_externa": e["estado_fuente_externa"], "fecha_estimada": None, "consultado": now()}

    @route("POST", "/notificaciones", "Envío simulado de un mensaje al afiliado")
    def _(q, b, **k):
        need(b, "caso_id", "mensaje"); find(EXP, "caso_id", b["caso_id"], "El expediente")
        n = {"notificacion_id": nid("NOT", "notificaciones"), **b, "estado": "ENVIO_SIMULADO", "fecha": now()}
        col("notificaciones").append(n); return 201, n

    @route("GET", "/notificaciones", "Lista las notificaciones simuladas")
    def _(q, b, **k): return col("notificaciones")

# ───────────────────────── Reto 04 · Ahorro voluntario
if RETO == "04":
    ALT, PER = load("alternativas_simuladas.csv"), load("personas_y_metas.csv")
    AVISO = "Simulación. La rentabilidad no es garantizada. No se crean cuentas ni transacciones."

    @route("GET", "/alternativas", "Catálogo simulado de alternativas de inversión")
    def _(q, b, **k): return ALT

    def validar(b):
        need(b, "alternativa_id", "aporte_COP", "periodicidad")
        a = find(ALT, "alternativa_id", b["alternativa_id"], "La alternativa"); minimo = int(float(a["minimo_aporte_COP_ejemplo"]))
        ok = float(b["aporte_COP"]) >= minimo
        return {"elegible": ok, "minimo_aporte_COP": minimo, "comision_pct_ejemplo": a["comision_pct_ejemplo"], "riesgo": a["riesgo"],
                "motivo": "Cumple el aporte mínimo de la alternativa." if ok else f"El aporte es menor al mínimo de {minimo} COP de esta alternativa.", "aviso": AVISO}

    @route("POST", "/planes/validar", "Valida el aporte contra el mínimo de la alternativa")
    def _(q, b, **k): return validar(b)

    @route("POST", "/metas", "Crea la meta y su plan simulado. Rechaza un aporte no elegible")
    def _(q, b, **k):
        need(b, "usuario_id", "objetivo", "monto_meta_COP", "plazo_meses"); v = validar(b)
        if not v["elegible"]:
            raise Err(422, v["motivo"], {"minimo_aporte_COP": v["minimo_aporte_COP"]})
        m = {"meta_id": nid("META", "metas"), **b, "estado": "PLAN_SIMULADO", "creada": now(), "aviso": AVISO}
        col("metas").append(m); return 201, m

    @route("GET", "/metas", "Lista las metas creadas. Filtro: ?usuario_id=")
    def _(q, b, **k): return [m for m in col("metas") if "usuario_id" not in q or m["usuario_id"] == q["usuario_id"][0]]

    @route("GET", "/panel/{id}", "Aportes, valorización simulada y progreso de un usuario de prueba")
    def _(q, b, id):
        p = find(PER, "usuario_id", id, "El usuario"); ap, val, meta = float(p["aportado_acumulado_COP_ficticio"]), float(p["valorizacion_simulada_COP"]), float(p["monto_meta_COP"])
        return {**p, "total_ilustrativo_COP": ap + val, "progreso_pct": round((ap + val) / meta * 100, 1), "metas_creadas": [m for m in col("metas") if m["usuario_id"] == id], "aviso": AVISO}

# ───────────────────────── Reto 05 · Radicación
if RETO == "05":
    REQ = load("requisitos_documentales.csv")

    @route("GET", "/requisitos", "Lista de requisitos. Filtro: ?tipo=PENSION_INVALIDEZ")
    def _(q, b, **k): return REQ

    @route("POST", "/solicitudes", "Crea un borrador y retorna solicitud_id")
    def _(q, b, **k):
        need(b, "documento_solicitante")
        s = {"solicitud_id": nid("SOL", "solicitudes"), **b, "estado": "BORRADOR", "avance": {}, "beneficiarios": [], "creada": now()}
        col("solicitudes").append(s); return 201, s

    @route("GET", "/solicitudes", "Lista las solicitudes")
    def _(q, b, **k): return col("solicitudes")

    @route("GET", "/solicitudes/{id}", "Retorna la solicitud con su avance guardado")
    def _(q, b, id): return find(col("solicitudes"), "solicitud_id", id, "La solicitud")

    @route("PUT", "/solicitudes/{id}/avance", "Guarda el avance. Se conserva aunque el servicio se reinicie")
    def _(q, b, id):
        s = find(col("solicitudes"), "solicitud_id", id, "La solicitud")
        if s["estado"] == "RADICADA": raise Err(409, "La solicitud ya está radicada")
        s["avance"].update(b); s["actualizada"] = now(); return s

    @route("POST", "/solicitudes/{id}/beneficiarios", "Registra uno o varios beneficiarios en una sola operación. Cuerpo: objeto o lista")
    def _(q, b, id):
        s = find(col("solicitudes"), "solicitud_id", id, "La solicitud"); lote = b if isinstance(b, list) else [b]
        for x in lote: need(x, "nombre", "documento", "parentesco")
        docs = {x["documento"] for x in s["beneficiarios"]}; rep = [x["documento"] for x in lote if x["documento"] in docs]
        if rep or len({x["documento"] for x in lote}) < len(lote):
            raise Err(409, "Hay beneficiarios repetidos. No se registró ninguno.", {"repetidos": rep})
        s["beneficiarios"] += lote; s["actualizada"] = now(); return 201, {"registrados": len(lote), "total": len(s["beneficiarios"])}

    @route("POST", "/solicitudes/{id}/radicar", "Radica solo si validaciones = OK")
    def _(q, b, id):
        s = find(col("solicitudes"), "solicitud_id", id, "La solicitud"); need(b, "validaciones")
        if s["estado"] == "RADICADA": raise Err(409, "La solicitud ya está radicada", {"radicado": s["radicado"]})
        if b["validaciones"] != "OK": raise Err(422, "No se radica: las validaciones no están en OK.")
        n = sum(1 for x in col("solicitudes") if x["estado"] == "RADICADA") + 1
        s.update(estado="RADICADA", radicado=f"RAD-SIM-2026-{n:05d}", radicada=now()); return s


@route("POST", "/_reset", "Borra el estado guardado y deja el servicio como al inicio")
def _(q, b, **k):
    STATE.clear(); return {"estado": "reiniciado"}


class H(BaseHTTPRequestHandler):
    def send(self, code, obj):
        raw = json.dumps(obj, ensure_ascii=False, indent=1).encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*"); self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS"); self.send_header("Content-Length", str(len(raw)))
        self.end_headers(); self.wfile.write(raw)

    def handle_any(self):
        try: raw_path = self.path.encode("latin-1").decode("utf-8")
        except UnicodeError: raw_path = self.path
        u = urlparse(raw_path); path = u.path.rstrip("/") or "/"; q = parse_qs(u.query)
        if self.command == "OPTIONS": return self.send(204, {})
        if path == "/":
            return self.send(200, {"servicio": f"Mock del reto {RETO} · datos sintéticos", "operaciones": [{"operacion": f"{m} {p}", "que_hace": d} for m, _, p, d, _ in ROUTES]})
        try:
            body = {}
            n = int(self.headers.get("Content-Length") or 0)
            if n:
                try: body = json.loads(self.rfile.read(n).decode("utf-8"))
                except ValueError: raise Err(400, "El cuerpo no es JSON válido")
            hit = False
            for m, rx, _, _, fn in ROUTES:
                mt = rx.match(path)
                if mt:
                    hit = True
                    if m == self.command:
                        res = fn(q, body, **mt.groupdict()); code, obj = res if isinstance(res, tuple) else (200, res)
                        if self.command != "GET": save()
                        return self.send(code, obj)
            raise Err(405 if hit else 404, "Método no permitido para esta ruta" if hit else "Ruta no encontrada. Consulte GET / para ver las operaciones")
        except Err as x:
            self.send(x.code, {"error": x.msg, **x.extra})
        except Exception as x:  # el mock nunca debe caerse en plena demo
            self.send(500, {"error": "Error interno del mock", "detalle": str(x)})

    do_GET = do_POST = do_PUT = do_OPTIONS = handle_any

    def log_message(self, fmt, *a):
        sys.stderr.write(f"[{now()}] {self.command} {self.path} -> {a[1] if len(a) > 1 else ''}\n")


if __name__ == "__main__":
    print(f"Mock del reto {RETO} en http://localhost:{PORT}   (GET / lista las operaciones · Ctrl+C para detener)")
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
