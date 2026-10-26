import os, secrets, string, sqlite3
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, request, redirect, url_for, render_template_string, session, flash, abort

APP_SECRET = os.environ.get("APP_SECRET", "change-this-before-public-launch")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Bless@2008")
DB_PATH = os.environ.get("DB_PATH", "shipments.db")

app = Flask(__name__)
app.secret_key = APP_SECRET

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

def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

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
@media(max-width:580px){form.search{flex-direction:column}.panel{padding:18px}header{padding:18px}nav a{margin-left:8px}}
"""
BASE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{ title }} | Newton Logistics</title><style>""" + STYLE + """</style></head><body>
<header><div class="brand">NEWTON <span>LOGISTICS</span></div><nav><a href="{{ url_for('index') }}">Track package</a>{% if session.get('admin') %}<a href="{{ url_for('admin') }}">Dashboard</a><a href="{{ url_for('logout') }}">Log out</a>{% else %}<a href="{{ url_for('login') }}">Admin</a>{% endif %}</nav></header>
<main>{% with messages=get_flashed_messages() %}{% for m in messages %}<div class="flash">{{ m }}</div>{% endfor %}{% endwith %}{{ content|safe }}</main><footer>Newton Logistics · Tracking information reflects the latest recorded update. This website is not affiliated with another courier unless explicitly stated.</footer></body></html>"""

def page(title, content, **ctx):
    return render_template_string(BASE, title=title, content=render_template_string(content, **ctx), **ctx)

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
<section class="hero"><h1>Your shipment, in view.</h1><p>Enter your tracking code to view the latest recorded shipment status and location.</p>
<form class="search" method="post"><input name="code" placeholder="e.g. NWT-AB12CD34" value="{{ code }}" required aria-label="Tracking code"><button>Track shipment</button></form></section>
{% if searched %}
<div class="panel">
{% if shipment %}
<div class="muted">TRACKING NUMBER</div><div class="tracking-code">{{ shipment.code }}</div><p><span class="pill">{{ shipment.status }}</span></p>
<div class="grid"><div><div class="muted">LATEST RECORDED LOCATION</div><strong>{{ shipment.location }}</strong></div><div><div class="muted">DESTINATION</div><strong>{{ shipment.destination }}</strong></div><div><div class="muted">ORIGIN</div><strong>{{ shipment.origin }}</strong></div><div><div class="muted">LAST UPDATED</div><strong>{{ shipment.updated_at }}</strong></div></div>
{% if shipment.details %}<p>{{ shipment.details }}</p>{% endif %}
<p class="muted">This shows the latest information recorded by the shipping service; it is not live GPS tracking.</p>
{% else %}<h2>Tracking code not found</h2><p>Please check the code and try again, or contact the sender.</p>{% endif %}
</div>{% endif %}
<div class="panel"><h2>How tracking works</h2><p class="muted">Each valid code links to a shipment record. Status and location appear here after the administrator records an update.</p></div>
"""
    return page("Track a package", content, shipment=shipment, searched=searched, code=code)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if secrets.compare_digest(request.form.get("password", ""), ADMIN_PASSWORD):
            session["admin"] = True
            return redirect(url_for("admin"))
        flash("Incorrect password.")
    return page("Admin login", """
<div class="panel" style="max-width:480px;margin:0 auto"><h1 style="font-size:28px">Admin sign in</h1><p class="muted">Private shipment management</p>
<form method="post"><div class="field"><label>Admin password</label><input type="password" name="password" required autocomplete="current-password"></div><button>Sign in</button></form></div>
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
        allowed = ["Processing", "In Transit", "At Local Facility", "Out for Delivery", "Delivered", "On Hold"]
        if not all([recipient, origin, destination, location]) or status not in allowed:
            flash("Fill in all required fields and choose a valid status.")
        else:
            try:
                with db() as conn:
                    conn.execute("INSERT INTO shipments(code,recipient,origin,destination,status,location,details,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                        (code, recipient, origin, destination, status, location, details, now()))
                flash("Shipment created. Tracking code: " + code)
                return redirect(url_for("admin"))
            except sqlite3.IntegrityError:
                flash("That tracking code already exists. Choose another one.")
    with db() as conn:
        shipments = conn.execute("SELECT * FROM shipments ORDER BY id DESC").fetchall()
    return page("Admin dashboard", """
<div class="panel"><h1 style="font-size:30px">Shipment dashboard</h1><p class="muted">Create a shipment record and share its tracking code with the customer.</p>
<form method="post">
<div class="grid">
<div class="field"><label>Recipient / reference *</label><input name="recipient" required></div>
<div class="field"><label>Tracking code (optional)</label><input name="code" placeholder="Leave blank to generate one"></div>
<div class="field"><label>Origin *</label><input name="origin" placeholder="City or dispatch location" required></div>
<div class="field"><label>Destination *</label><input name="destination" placeholder="Destination city / facility" required></div>
<div class="field"><label>Current recorded location *</label><input name="location" placeholder="Where the package was last confirmed" required></div>
<div class="field"><label>Status *</label><select name="status">{% for s in statuses %}<option>{{ s }}</option>{% endfor %}</select></div>
</div>
<div class="field"><label>Shipment update / notes</label><textarea name="details" placeholder="Optional note based on confirmed information"></textarea></div><button>Create shipment</button>
</form></div>
<div class="panel"><h2>Saved shipments ({{ shipments|length }})</h2>
{% if shipments %}<div style="overflow-x:auto"><table><thead><tr><th>Code</th><th>Destination</th><th>Status</th><th>Location</th><th>Updated</th><th></th></tr></thead><tbody>
{% for s in shipments %}<tr><td><strong>{{ s.code }}</strong></td><td>{{ s.destination }}</td><td>{{ s.status }}</td><td>{{ s.location }}</td><td>{{ s.updated_at }}</td><td><a href="{{ url_for('edit', code=s.code) }}">Edit</a></td></tr>{% endfor %}
</tbody></table></div>{% else %}<p class="muted">No shipments yet. Create the first one above.</p>{% endif %}</div>
""", shipments=shipments, statuses=["Processing","In Transit","At Local Facility","Out for Delivery","Delivered","On Hold"])

@app.route("/admin/edit/<code>", methods=["GET", "POST"])
@admin_required
def edit(code):
    with db() as conn:
        shipment = conn.execute("SELECT * FROM shipments WHERE code=?", (code.upper(),)).fetchone()
    if not shipment:
        abort(404)
    statuses = ["Processing","In Transit","At Local Facility","Out for Delivery","Delivered","On Hold"]
    if request.method == "POST":
        status = request.form.get("status", "Processing")
        location = request.form.get("location", "").strip()
        details = request.form.get("details", "").strip()
        if status not in statuses or not location:
            flash("Enter a location and valid status.")
        else:
            with db() as conn:
                conn.execute("UPDATE shipments SET status=?,location=?,details=?,updated_at=? WHERE code=?",
                             (status, location, details, now(), code.upper()))
            flash("Shipment updated.")
            return redirect(url_for("admin"))
    return page("Update shipment", """
<div class="panel"><h1 style="font-size:28px">Update {{ shipment.code }}</h1><p>Destination: <strong>{{ shipment.destination }}</strong></p>
<form method="post"><div class="field"><label>Status</label><select name="status">{% for s in statuses %}<option {% if s==shipment.status %}selected{% endif %}>{{ s }}</option>{% endfor %}</select></div>
<div class="field"><label>Latest confirmed location</label><input name="location" value="{{ shipment.location }}" required></div>
<div class="field"><label>Update notes</label><textarea name="details">{{ shipment.details }}</textarea></div><div class="actions"><button>Save update</button><a class="btn" style="background:#64748b" href="{{ url_for('admin') }}">Cancel</a></div></form>
<p class="muted">Only enter a location/status supported by actual shipment information.</p></div>
""", shipment=shipment, statuses=statuses)

@app.route("/health")
def health():
    return {"status": "ok"}

init_db()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
