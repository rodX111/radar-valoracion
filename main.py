from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel 
from sqlalchemy import create_engine, text
import pandas as pd
import hashlib
import jwt # NUEVA LIBRERÍA
from datetime import datetime, timedelta

app = FastAPI()

# 1. Define primero la lista de sitios permitidos
origins = [
    "https://radarvaloracion.com",
    "https://www.radarvaloracion.com",
    "http://localhost:5500",  # Para cuando pruebes en tu compu
    "http://127.0.0.1:5500",
]

# 2. Pasa esa lista al middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # <-- Aquí usamos la lista que creamos arriba
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_URL = "postgresql://postgres.mayauvnugqgxgffxvdgi:Guate%402021xyz@aws-1-us-east-1.pooler.supabase.com:6543/postgres"
motor = create_engine(DB_URL)

SECRET_KEY = "mi_clave_super_secreta_radar" # El sello para que nadie falsifique tus tokens

class LoginRequest(BaseModel):
    username: str
    password: str
 
class PortafolioRequest(BaseModel):
    ticker: str

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# --- NUEVO: CREAR Y VERIFICAR PULSERAS VIP ---
def crear_token(usuario_id: int):
    # El token dura 24 horas
    expiracion = datetime.utcnow() + timedelta(days=1)
    return jwt.encode({"sub": str(usuario_id), "exp": expiracion}, SECRET_KEY, algorithm="HS256")

def verificar_token(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Acceso denegado. Falta tu Token VIP.")
    
    token = authorization.split(" ")[1] # Extraemos la pulsera
    try:
        # Verificamos que sea auténtica
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return int(payload.get("sub")) # Devolvemos el ID del usuario
    except:
        raise HTTPException(status_code=401, detail="Token falso o expirado.")
        
# --- 4. MOTOR DE CÁLCULOS (El Doctor Financiero) ---
def calcular_salud_financiera(df):
    if 'Activo Circulante' in df.columns and not df.empty:
        # Evitamos divisiones por cero
        pas_circ = df['Pasivo Circulante'].replace(0, 1).fillna(1)
        act_tot = df['Activo Total'].replace(0, 1).fillna(1)
        ventas = df['Ventas Totales'].replace(0, 1).fillna(1)
        gastos_int = df['Gastos por Intereses'].replace(0, 1).fillna(1)

        # Calculamos las 5 métricas
        df['PA'] = (df['Activo Circulante'].fillna(0) - df['Inventario'].fillna(0)) / pas_circ
        df['RC'] = df['Activo Circulante'].fillna(0) / pas_circ
        df['END'] = df['Pasivo Total'].fillna(0) / act_tot
        df['MN'] = df['Utilidad Neta'].fillna(0) / ventas
        df['CI'] = df['EBIT'].fillna(0) / gastos_int

        # Evaluamos la regla estricta (Todo Verde)
        df['Todo_Verde'] = (df['PA'] >= 1) & (df['RC'] >= 1.5) & (df['END'] < 0.50) & (df['MN'] > 0.10) & (df['CI'] > 3)
        
        # Asignamos la etiqueta
        df['Salud Financiera'] = df['Todo_Verde'].apply(lambda x: '🟢 Impecable' if x else '🟡 Con Riesgos')
    else:
        df['Salud Financiera'] = 'Pendiente'
        
    return df
    
# --- RUTAS ---
@app.post("/api/login")
def iniciar_sesion(request: LoginRequest):
    try:
        with motor.connect() as conn:
            query = text("SELECT id, username FROM usuarios WHERE username=:u AND password=:p")
            resultado = conn.execute(query, {"u": request.username, "p": hash_password(request.password)}).fetchone()
            
            if resultado:
                usuario_id = resultado[0]
                token_real = crear_token(usuario_id) # Creamos la pulsera matemática
                return {"estado": "éxito", "mensaje": "Bienvenido", "token": token_real}
            else:
                raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

#Ruta gratuita
@app.get("/api/acciones")
def obtener_acciones_publicas():
    try:
        query = 'SELECT * FROM acciones_maestro WHERE "Upside Potencial" > 0 ORDER BY "Upside Potencial" DESC'
        df = pd.read_sql(query, con=motor)
        
        # 🛑 NUEVO: Hacemos el diagnóstico financiero al vuelo
        df = calcular_salud_financiera(df)
        
        datos_json = df.to_dict(orient="records")
        return {"estado": "éxito", "acciones": datos_json}
    except Exception as e:
        return {"estado": "error", "mensaje": str(e)}
        
# NUEVO: Ruta protegida. Obliga a que FastAPI ejecute 'verificar_token' antes de continuar
@app.get("/api/mi-portafolio")
def obtener_portafolio(usuario_id: int = Depends(verificar_token)):
    try:
        query = text("""
            SELECT a.* FROM acciones_maestro a
            JOIN portafolios p ON a."Ticker" = p.ticker
            WHERE p.usuario_id = :uid
        """)
        df = pd.read_sql(query, con=motor, params={"uid": usuario_id})
        
        # 🛑 NUEVO: Hacemos el diagnóstico para las acciones del usuario
        df = calcular_salud_financiera(df)
        
        datos_json = df.to_dict(orient="records")
        return {"estado": "éxito", "acciones": datos_json}
    except Exception as e:
        return {"estado": "error", "mensaje": str(e)}

# ==========================================
# RUTA: AGREGAR AL PORTAFOLIO (Con lógica Freemium)
# ==========================================
@app.post("/api/agregar-portafolio")
def agregar_portafolio(request: PortafolioRequest, usuario_id: int = Depends(verificar_token)):
    try:
        with motor.connect() as conn:
            # 1. Contamos cuántas acciones ya tiene este usuario
            query_conteo = text("SELECT COUNT(*) FROM portafolios WHERE usuario_id = :uid")
            cantidad = conn.execute(query_conteo, {"uid": usuario_id}).scalar()

            # 2. LA REGLA DE ORO (Freemium)
            if cantidad >= 5:
                return {
                    "estado": "paywall", 
                    "mensaje": "Has alcanzado el límite de 5 seguimientos gratuitos. ¡Adquiere Radar PRO para alertas ilimitadas!"
                }

            # 3. Verificamos que no la haya agregado antes
            query_existe = text("SELECT id FROM portafolios WHERE usuario_id = :uid AND ticker = :t")
            existe = conn.execute(query_existe, {"uid": usuario_id, "t": request.ticker}).fetchone()
            
            if existe:
                return {"estado": "info", "mensaje": f"Ya estás siguiendo a {request.ticker}."}

            # 4. Si tiene menos de 5 y no existe, la guardamos
            query_insert = text("INSERT INTO portafolios (usuario_id, ticker) VALUES (:uid, :t)")
            conn.execute(query_insert, {"uid": usuario_id, "t": request.ticker})
            conn.commit()
            
            return {"estado": "éxito", "mensaje": f"¡{request.ticker} agregada! Te avisaremos por Telegram."}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
 # ==========================================
# RUTA: REGISTRO DE NUEVOS USUARIOS
# ==========================================
@app.post("/api/registro")
def registrar_usuario(request: LoginRequest): # Reutilizamos el modelo de Login
    try:
        with motor.connect() as conn:
            # 1. Verificar si el usuario ya existe
            query_existe = text("SELECT id FROM usuarios WHERE username = :u")
            existe = conn.execute(query_existe, {"u": request.username}).fetchone()
            
            if existe:
                raise HTTPException(status_code=400, detail="El nombre de usuario ya está en uso.")
            
            # 2. Insertar nuevo usuario con contraseña hasheada
            query_insert = text("INSERT INTO usuarios (username, password) VALUES (:u, :p)")
            conn.execute(query_insert, {
                "u": request.username, 
                "p": hash_password(request.password) # Usamos tu función de encriptación
            })
            conn.commit()
            
            return {"estado": "éxito", "mensaje": "Cuenta creada exitosamente. ¡Ya puedes iniciar sesión!"}
            
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))
        
# ==========================================
# RUTA: ELIMINAR ACCIÓN DEL PORTAFOLIO
# ==========================================
@app.delete("/api/eliminar-portafolio/{ticker}")
def eliminar_portafolio(ticker: str, usuario_id: int = Depends(verificar_token)):
    try:
        with motor.connect() as conn:
            # 1. Ejecutamos la eliminación filtrando por usuario y ticker
            # Esto evita que un usuario borre por error la acción de otro
            query_delete = text("""
                DELETE FROM portafolios 
                WHERE usuario_id = :uid AND ticker = :t
            """)
            
            resultado = conn.execute(query_delete, {"uid": usuario_id, "t": ticker})
            conn.commit()

            # 2. Verificamos si realmente se borró algo
            if resultado.rowcount == 0:
                raise HTTPException(status_code=404, detail="No se encontró la acción en tu portafolio.")

            return {"estado": "éxito", "mensaje": f"Se ha dejado de seguir a {ticker}."}
            
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))
