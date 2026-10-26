import os
import secrets
import string
import sqlite3
from datetime import datetime, timezone
from functools import wraps

import cloudinary
import cloudinary.uploader
from flask import (
    Flask, request, redirect, url_for, render_template_string,
    session, flash, abort
)

APP_SECRET = os.environ.get("APP_SECRET", "change-this-before-public-launch")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Bless@2008")
DB_PATH = os.environ.get("DB_PATH", "shipments.db")
CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET", "")

app = Flask(__name__)
app.secret_key = APP_SECRET
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # max 8 MB upload

def cloudinary_ready():
    return all([CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET])

def configure_cloudinary():
    if cloudinary_ready():
        cloudinary.config(
            cloud_name=CLOUDINARY_CLOUD_NAME,
            api_key=CLOUDINARY_API_KEY,
            api_secret=CLOUDINARY_API_SECRET,
            secure=True,
        )

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS shipments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            recipient TEXT NOT NULL,
            origin TEXT NOT NULL,
            destination TEXT NOT NULL,
            status TEXT NOT NULL,
            location TEXT NOT NULL,
            details TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        )""")
        # Safe migration: preserve existing shipments and add the photo column if missing.
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(shipments)").fetchall()}
        if "photo_url" not in columns:
            conn.execute("ALTER TABLE shipments ADD COLUMN photo_url TEXT NOT NULL DEFAULT ''")

def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def upload_photo(file_storage):
    """Upload an optional image to Cloudinary and return its secure URL."""
    if not file_storage or not file_storage.filename:
        return None
    if not cloudinary_ready():
        raise RuntimeError("Faltan las credenciales de Cloudinary en Render.")
    allowed = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if file_storage.mimetype not in allowed:
        raise ValueError("Usa una imagen JPG, PNG, WEBP o GIF.")
    configure_cloudinary()
    result = cloudinary.uploader.upload(
        file_storage,
        folder="newton-logistics/parcels",
        resource_type="image",
        transformation=[{"width": 1600, "height": 1600, "crop": "limit"}],
    )
    return result.get("secure_url")

STYLE = """
:root{--navy:#10233f;--blue:#1d5eea;--pale:#f3f6fb;--ink:#172033;--muted:#68758a;--line:#e2e8f0}
*{box-sizing:border-box}body{margin:0;font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif;background:var(--pale);color:var(--ink)}
header{background:var(--navy);color:white;padding:20px 5%;display:flex;align-items:center;justify-content:space-between;gap:15px;flex-wrap:wrap}
.brand{font-weight:850;letter-spacing:.3px;font-size:20px}.brand span{color:#79a7ff}
nav a{color:white;text-decoration:none;margin-left:16px;font-size:14px}
main{max-width:1050px;margin:38px auto;padding:0 18px}.hero{background:linear-gradient(135deg,#10233f,#1c4c91);color:white;border-radius:22px;padding:38px 26px;text-align:center}
h1{margin:0 0 12px;font-size:clamp(28px,5vw,43px)}.hero p{color:#dbe7ff;line-height:1.6}
.panel{background:white;border:1px solid var(--line);border-radius:18px;padding:24px;margin-top:22px;box-shadow:0 8px 28px #152b4810}
form.search{display:flex;gap:10px;max-width:650px;margin:25px auto 0}input,select,textarea{width:100%;padding:12px 13px;border:1px solid #cbd5e1;border-radius:10px;font:inherit;background:white}
textarea{min-height:90px}button,.btn{border:0;background:var(--blue);color:white;padding:12px 17px;border-radius:10px;font-weight:700;font:inherit;cursor:pointer;text-decoration:none;display:inline-block}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}.field{display:flex;flex-direction:column;gap:7px;margin:10px 0}.field label{font-weight:650;font-size:14px}
.muted{color:var(--muted);font-size:14px}.pill{display:inline-block;background:#e9f1ff;color:#1748a6;border-radius:999px;padding:7px 12px;font-weight:750;font-size:13px}
.flash{padding:12px 14px;border-radius:10px;background:#fff4d6;margin:10px 0}.tracking-code{font-size:22px;font-weight:850;letter-spacing:1px;overflow-wrap:anywhere}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:12px 8px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--muted)}
footer{text-align:center;color:var(--muted);padding:30px 15px;font-size:13px}
a{color:#1d5eea}.actions{display:flex;gap:8px;flex-wrap:wrap}
.parcel-photo{display:block;width:100%;max-width:560px;max-height:480px;object-fit:contain;border-radius:14px;border:1px solid var(--line);margin:18px auto;background:#f8fafc}
@media(max-width:580px){form.search{flex-direction:column}.panel{padding:18px}header{padding:18px}nav a{margin-left:8px}}
"""
BASE = """<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{ title }} | Newton Logistics</title><style>""" + STYLE + """</style></head><body>
<header><div class="brand">NEWTON <span>LOGISTICS</span></div><nav><a href="{{ url_for('index') }}">Seguimiento</a>{% if session.get('admin') %}<a href="{{ url_for('admin') }}">Panel de administración</a><a href="{{ url_for('logout') }}">Cerrar sesión</a>{% else %}<a href="{{ url_for('login') }}">Administración</a>{% endif %}</nav></header>
<main>{% with messages=get_flashed_messages() %}{% for m in messages %}<div class="flash">{{ m }}</div>{% endfor %}{% endwith %}{{ content|safe }}</main><footer>Newton Logistics · La información de seguimiento refleja la última actualización registrada. Este sitio no está afiliado a otra empresa de mensajería, salvo que se indique expresamente.</footer></body></html>"""

def page(title, content, **ctx):
    return render_template_string(BASE, title=title, content=render_template_string(content, **ctx), **ctx)

STATUSES = ["Processing", "In Transit", "At Local Facility", "Out for Delivery", "Delivered", "On Hold"]

def status_es(status):
    return {
        "Processing": "En preparación",
        "In Transit": "En tránsito",
        "At Local Facility": "En el centro de distribución local",
        "Out for Delivery": "En camino para la entrega",
        "Delivered": "Entregado",
        "On Hold": "En espera",
    }.get(status, status)

@app.route("/", methods=["GET", "POST"])
def index():
    shipment = None
    searched = False
    code = ""
    if request.method == "POST":
        searched = True
        code = request.form.get("code", "").strip().upper()
        with db() as conn:
            shipment = conn.execute("SELECT * FROM shipments WHERE code=?", (code,)).fetchone()
    content = """
<section class="hero">
<h1>Consulta el estado de tu envío</h1>
<p>Introduce tu código de seguimiento para consultar el último estado y la ubicación registrada de tu envío.</p>
<form class="search" method="post">
<input name="code" placeholder="Ej.: NWT-AB12CD34" value="{{ code }}" required aria-label="Código de seguimiento">
<button>Consultar envío</button></form></section>
{% if searched %}<div class="panel">{% if shipment %}
<div class="muted">NÚMERO DE SEGUIMIENTO</div><div class="tracking-code">{{ shipment.code }}</div>
<p><span class="pill">{{ status_es(shipment.status) }}</span></p>
{% if shipment.photo_url %}<h2>Foto del paquete</h2><img class="parcel-photo" src="{{ shipment.photo_url }}" alt="Foto del paquete">{% endif %}
<div class="grid">
<div><div class="muted">ÚLTIMA UBICACIÓN REGISTRADA</div><strong>{{ shipment.location }}</strong></div>
<div><div class="muted">DESTINO</div><strong>{{ shipment.destination }}</strong></div>
<div><div class="muted">ORIGEN</div><strong>{{ shipment.origin }}</strong></div>
<div><div class="muted">ÚLTIMA ACTUALIZACIÓN</div><strong>{{ shipment.updated_at }}</strong></div></div>
{% if shipment.details %}<p>{{ shipment.details }}</p>{% endif %}
<p class="muted">Esta información refleja la última actualización registrada. No se trata de un seguimiento GPS en tiempo real.</p>
{% else %}<h2>No se encontró el código de seguimiento</h2><p>Comprueba el código e inténtalo de nuevo o ponte en contacto con la persona que te envió el paquete.</p>{% endif %}</div>{% endif %}
<div class="panel"><h2>¿Cómo funciona el seguimiento?</h2><p class="muted">Cada código válido corresponde a un registro de envío. El estado y la ubicación se muestran aquí cuando se registra una actualización.</p></div>
"""
    return page("Seguimiento de envíos", content, shipment=shipment, searched=searched, code=code, status_es=status_es)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if secrets.compare_digest(request.form.get("password", ""), ADMIN_PASSWORD):
            session["admin"] = True
            return redirect(url_for("admin"))
        flash("Contraseña incorrecta.")
    return page("Acceso de administración", """
<div class="panel" style="max-width:480px;margin:0 auto"><h1 style="font-size:28px">Iniciar sesión</h1><p class="muted">Gestión privada de envíos</p>
<form method="post"><div class="field"><label>Contraseña de administrador</label><input type="password" name="password" required autocomplete="current-password"></div><button>Entrar</button></form></div>
""")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

def new_code():
    alphabet = string.ascii_uppercase + string.digits
    with db() as conn:
        for _ in range(10):
            code = "NWT-" + "".join(secrets.choice(alphabet) for _ in range(8))
            if not conn.execute("SELECT 1 FROM shipments WHERE code=?", (code,)).fetchone():
                return code
    raise RuntimeError("Could not create a unique code")

@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin():
    if request.method == "POST":
        recipient = request.form.get("recipient", "").strip()
        origin = request.form.get("origin", "").strip()
        destination = request.form.get("destination", "").strip()
        status = request.form.get("status", "Processing").strip()
        location = request.form.get("location", "").strip()
        details = request.form.get("details", "").strip()
        code = request.form.get("code", "").strip().upper() or new_code()
        photo = request.files.get("photo")
        if not all([recipient, origin, destination, location]) or status not in STATUSES:
            flash("Completa todos los campos obligatorios y selecciona un estado válido.")
        else:
            photo_url = ""
            photo_warning = ""
            # Save the shipment even if the optional photo upload fails.
            # The full exception goes to Render Logs; never expose credentials to visitors.
            if photo and photo.filename:
                try:
                    photo_url = upload_photo(photo) or ""
                except Exception as exc:
                    app.logger.exception("Cloudinary photo upload failed while creating shipment")
                    photo_warning = " El envío se guardó, pero la foto no se pudo subir. Revisa Cloudinary en Render Logs."
            try:
                with db() as conn:
                    conn.execute("""INSERT INTO shipments(code,recipient,origin,destination,status,location,details,updated_at,photo_url)
                        VALUES(?,?,?,?,?,?,?,?,?)""",
                        (code, recipient, origin, destination, status, location, details, now(), photo_url))
                if photo_warning:
                    flash("Envío creado sin foto. Código de seguimiento: " + code + "." + photo_warning)
                else:
                    flash("Envío creado. Código de seguimiento: " + code)
                return redirect(url_for("admin"))
            except sqlite3.IntegrityError:
                flash("Ese código de seguimiento ya existe. Elige otro.")
            except Exception:
                app.logger.exception("Database error while creating shipment")
                flash("No se pudo guardar el envío. Revisa el error de base de datos en Render Logs.")
    with db() as conn:
        shipments = conn.execute("SELECT * FROM shipments ORDER BY id DESC").fetchall()
    return page("Panel de administración", """
<div class="panel"><h1 style="font-size:30px">Panel de envíos</h1><p class="muted">Crea un envío, añade una foto del paquete y comparte el código con el cliente.</p>
<form method="post" enctype="multipart/form-data"><div class="grid">
<div class="field"><label>Destinatario / referencia *</label><input name="recipient" required></div>
<div class="field"><label>Código de seguimiento (opcional)</label><input name="code" placeholder="Déjalo vacío para generar uno"></div>
<div class="field"><label>Origen *</label><input name="origin" placeholder="Ciudad o lugar de despacho" required></div>
<div class="field"><label>Destino *</label><input name="destination" placeholder="Ciudad o centro de destino" required></div>
<div class="field"><label>Última ubicación confirmada *</label><input name="location" placeholder="Último lugar confirmado" required></div>
<div class="field"><label>Estado *</label><select name="status">{% for s in statuses %}<option value="{{ s }}">{{ status_es(s) }}</option>{% endfor %}</select></div>
</div><div class="field"><label>Foto del paquete (opcional)</label><input type="file" name="photo" accept="image/jpeg,image/png,image/webp,image/gif"><small class="muted">JPG, PNG, WEBP o GIF; máximo 8 MB.</small></div>
<div class="field"><label>Actualización del envío / notas</label><textarea name="details" placeholder="Nota opcional basada en información confirmada"></textarea></div><button>Crear envío</button></form></div>
<div class="panel"><h2>Envíos guardados ({{ shipments|length }})</h2>
{% if shipments %}<div style="overflow-x:auto"><table><thead><tr><th>Código</th><th>Destino</th><th>Estado</th><th>Foto</th><th>Ubicación</th><th>Actualizado</th><th></th></tr></thead><tbody>
{% for s in shipments %}<tr><td><strong>{{ s.code }}</strong></td><td>{{ s.destination }}</td><td>{{ status_es(s.status) }}</td><td>{% if s.photo_url %}Sí{% else %}No{% endif %}</td><td>{{ s.location }}</td><td>{{ s.updated_at }}</td><td><a href="{{ url_for('edit', code=s.code) }}">Editar</a></td></tr>{% endfor %}
</tbody></table></div>{% else %}<p class="muted">Todavía no hay envíos. Crea el primero arriba.</p>{% endif %}</div>
""", shipments=shipments, statuses=STATUSES, status_es=status_es)

@app.route("/admin/edit/<code>", methods=["GET", "POST"])
@admin_required
def edit(code):
    with db() as conn:
        shipment = conn.execute("SELECT * FROM shipments WHERE code=?", (code.upper(),)).fetchone()
    if not shipment:
        abort(404)
    if request.method == "POST":
        status = request.form.get("status", "Processing")
        location = request.form.get("location", "").strip()
        details = request.form.get("details", "").strip()
        photo = request.files.get("photo")
        if status not in STATUSES or not location:
            flash("Introduce una ubicación y selecciona un estado válido.")
        else:
            try:
                new_photo_url = upload_photo(photo) if photo and photo.filename else None
                with db() as conn:
                    if new_photo_url:
                        conn.execute("UPDATE shipments SET status=?,location=?,details=?,updated_at=?,photo_url=? WHERE code=?",
                                     (status, location, details, now(), new_photo_url, code.upper()))
                    else:
                        conn.execute("UPDATE shipments SET status=?,location=?,details=?,updated_at=? WHERE code=?",
                                     (status, location, details, now(), code.upper()))
                flash("Envío actualizado.")
                return redirect(url_for("admin"))
            except Exception:
                app.logger.exception("Error updating shipment")
                flash("No se pudo actualizar el envío. Revisa el error más reciente en Render Logs.")
    with db() as conn:
        shipment = conn.execute("SELECT * FROM shipments WHERE code=?", (code.upper(),)).fetchone()
    return page("Actualizar envío", """
<div class="panel"><h1 style="font-size:28px">Actualizar {{ shipment.code }}</h1><p>Destino: <strong>{{ shipment.destination }}</strong></p>
{% if shipment.photo_url %}<p class="muted">Foto actual:</p><img class="parcel-photo" src="{{ shipment.photo_url }}" alt="Foto actual del paquete">{% endif %}
<form method="post" enctype="multipart/form-data"><div class="field"><label>Estado</label><select name="status">{% for s in statuses %}<option value="{{ s }}" {% if s==shipment.status %}selected{% endif %}>{{ status_es(s) }}</option>{% endfor %}</select></div>
<div class="field"><label>Última ubicación confirmada</label><input name="location" value="{{ shipment.location }}" required></div>
<div class="field"><label>Notas de actualización</label><textarea name="details">{{ shipment.details }}</textarea></div>
<div class="field"><label>Subir/reemplazar foto del paquete (opcional)</label><input type="file" name="photo" accept="image/jpeg,image/png,image/webp,image/gif"><small class="muted">Si no seleccionas una foto nueva, la foto actual se conserva.</small></div>
<div class="actions"><button>Guardar actualización</button><a class="btn" style="background:#64748b" href="{{ url_for('admin') }}">Cancelar</a></div></form>
<p class="muted">Introduce únicamente una ubicación y un estado respaldados por información real del envío.</p></div>
""", shipment=shipment, statuses=STATUSES, status_es=status_es)

@app.errorhandler(413)
def too_large(_error):
    return "La imagen supera el límite de 8 MB. Elige una imagen más pequeña.", 413

@app.route("/health")
def health():
    return {"status": "ok"}

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
