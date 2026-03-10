from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from auth import create_access_token, decode_access_token, get_current_user
from config import ADMIN_USERNAME, ADMIN_PASSWORD
import sqlite3
import os
import uvicorn

# ── Rate limiter ──────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="CarsDataAPI", description="API de consulta de vehículos por patente")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Base de datos SQLite ──────────────────────────────────────
DB_PATH = os.getenv("DB_PATH", "vehicles.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vehicles (
            patente TEXT PRIMARY KEY,
            marca   TEXT NOT NULL,
            modelo  TEXT NOT NULL,
            anio    TEXT NOT NULL,
            color   TEXT,
            titular TEXT,
            motor   TEXT,
            tipo    TEXT DEFAULT 'auto'
        )
    ''')
    # Datos de ejemplo para demo
    sample = [
        ("AB123CD", "Toyota",     "Corolla XEI",    "2022", "Blanco",  "García, María",    "2.0L 4cil", "auto"),
        ("MO456TZ", "Honda",      "CB500F",          "2021", "Rojo",    "García, María",    "471cc",     "moto"),
        ("AC789FG", "Volkswagen", "Vento Highline",  "2020", "Negro",   "Pereyra, Julián",  "1.4T TSI",  "auto"),
        ("XY789AB", "Peugeot",    "208 Allure",      "2023", "Gris",    "Ruiz, Carlos",     "1.2T PureTech","auto"),
        ("MN456CD", "Honda",      "CB300R",          "2022", "Negro",   "Cruz, Valentina",  "286cc",     "moto"),
        ("GH345IJ", "Ford",       "Ka SE",           "2021", "Blanco",  "Aguirre, Hernán",  "1.5L",      "auto"),
        ("IJ678KL", "Fiat",       "Cronos Drive",    "2023", "Plata",   "Vega, Natalia",    "1.3L",      "auto"),
        ("LM234NO", "Volkswagen", "Polo MSI",        "2022", "Azul",    "Ríos, Pablo",      "1.6L",      "auto"),
        ("EF012GH", "Volkswagen", "Vento Comfortline","2020","Negro",   "Díaz, Maximiliano","1.4T TSI",  "auto"),
        ("KL901MN", "Chevrolet",  "Onix LTZ",        "2022", "Rojo",    "Morales, Gustavo", "1.2T",      "auto"),
        ("CD789EF", "Renault",    "Sandero Stepway",  "2021","Naranja", "Gómez, Florencia", "1.6L",      "auto"),
        ("BC456DE", "Toyota",     "Hilux SRX",       "2023", "Blanco",  "Leiva, Roberto",   "2.8L Diesel","auto"),
        ("DE567FG", "Yamaha",     "MT-07",           "2022", "Gris",    "Ramírez, Sofía",   "689cc",     "moto"),
        ("FG678HI", "BMW",        "R1250 GS",        "2021", "Negro",   "Fernández, Diego", "1254cc",    "moto"),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO vehicles VALUES (?,?,?,?,?,?,?,?)", sample
    )
    conn.commit()
    conn.close()

# Inicializar DB al arrancar
init_db()

# ── Endpoints ─────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "CarsDataAPI — Pase Seguro",
        "version": "2.0",
        "endpoints": {
            "consulta_patente": "/api/vehicle/{patente}",
            "login":            "/auth/login",
            "docs":             "/docs"
        }
    }

@app.get("/api/vehicle/{patente}")
@limiter.limit("30/minute")
def get_vehicle(patente: str, request: Request, user: dict = Depends(get_current_user)):
    patente_clean = patente.replace(" ", "").replace("-", "").upper()
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM vehicles WHERE patente = ?", (patente_clean,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"Patente {patente_clean} no encontrada")
    return {
        "patente":  row["patente"],
        "marca":    row["marca"],
        "modelo":   row["modelo"],
        "anio":     row["anio"],
        "color":    row["color"],
        "titular":  row["titular"],
        "motor":    row["motor"],
        "tipo":     row["tipo"],
        "fuente":   "PaseSeguro DB"
    }

@app.get("/api/vehicle/{patente}/public")
@limiter.limit("10/minute")
def get_vehicle_public(patente: str, request: Request):
    """Endpoint público sin autenticación — devuelve datos básicos"""
    patente_clean = patente.replace(" ", "").replace("-", "").upper()
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM vehicles WHERE patente = ?", (patente_clean,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"Patente {patente_clean} no encontrada")
    return {
        "patente": row["patente"],
        "marca":   row["marca"],
        "modelo":  row["modelo"],
        "anio":    row["anio"],
        "color":   row["color"],
        "tipo":    row["tipo"],
    }

@app.post("/auth/login")
def login(request_data: dict):
    username = request_data.get("username")
    password = request_data.get("password")
    if username != ADMIN_USERNAME or password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    token = create_access_token({"sub": username})
    return {"access_token": token, "token_type": "bearer"}

@app.get("/api/vehicles")
@limiter.limit("20/minute")
def list_vehicles(request: Request, user: dict = Depends(get_current_user)):
    """Lista todos los vehículos (solo admin)"""
    conn = get_db()
    rows = conn.execute("SELECT * FROM vehicles").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/vehicles")
@limiter.limit("20/minute")
def add_vehicle(vehicle: dict, request: Request, user: dict = Depends(get_current_user)):
    """Agregar un vehículo a la base de datos"""
    required = ["patente", "marca", "modelo", "anio"]
    for f in required:
        if f not in vehicle:
            raise HTTPException(status_code=400, detail=f"Campo requerido: {f}")
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO vehicles VALUES (?,?,?,?,?,?,?,?)",
            (
                vehicle["patente"].upper(),
                vehicle["marca"],
                vehicle["modelo"],
                vehicle["anio"],
                vehicle.get("color", ""),
                vehicle.get("titular", ""),
                vehicle.get("motor", ""),
                vehicle.get("tipo", "auto"),
            )
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Patente ya existe")
    finally:
        conn.close()
    return {"ok": True, "patente": vehicle["patente"].upper()}

@app.put("/api/vehicles/{patente}")
def update_vehicle(patente: str, vehicle: dict, user: dict = Depends(get_current_user)):
    """Actualizar datos de un vehículo"""
    conn = get_db()
    fields = {k: v for k, v in vehicle.items() if k != "patente"}
    if not fields:
        raise HTTPException(status_code=400, detail="Sin campos para actualizar")
    set_clause = ", ".join(f"{k}=?" for k in fields)
    values = list(fields.values()) + [patente.upper()]
    conn.execute(f"UPDATE vehicles SET {set_clause} WHERE patente=?", values)
    conn.commit()
    conn.close()
    return {"ok": True}

@app.delete("/api/vehicles/{patente}")
def delete_vehicle(patente: str, user: dict = Depends(get_current_user)):
    """Eliminar un vehículo"""
    conn = get_db()
    conn.execute("DELETE FROM vehicles WHERE patente=?", (patente.upper(),))
    conn.commit()
    conn.close()
    return {"ok": True}

# ── Arranque ──────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
