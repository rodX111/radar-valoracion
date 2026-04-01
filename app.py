import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine, text
import hashlib

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Radar de Valor", page_icon="🎯", layout="wide")

# ==========================================
# 1. MOTOR DE BASE DE DATOS Y USUARIOS (NUBE)
# ==========================================
# Llamamos a la bóveda secreta de Streamlit
DB_URL = st.secrets["DB_URL"]
motor = create_engine(DB_URL)

def init_db():
    with motor.connect() as conn:
        # PostgreSQL usa SERIAL en lugar de AUTOINCREMENT
        conn.execute(text('''CREATE TABLE IF NOT EXISTS usuarios 
                     (id SERIAL PRIMARY KEY, username TEXT UNIQUE, password TEXT)'''))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS portafolios 
                     (id SERIAL PRIMARY KEY, usuario_id INTEGER, ticker TEXT, 
                     FOREIGN KEY(usuario_id) REFERENCES usuarios(id))'''))
        conn.commit()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

init_db()

# Variables de Sesión
if 'usuario_id' not in st.session_state:
    st.session_state['usuario_id'] = None
    st.session_state['username'] = None

# --- CARGAR DATOS DEL ROBOT ---
# Apagamos el caché temporalmente con (ttl=0) para forzar la recarga
@st.cache_data(ttl=0)
def cargar_datos_maestros():
    try:
        df = pd.read_sql("SELECT * FROM acciones_maestro", motor)
        return df, None
    except Exception as e:
        # Si falla, devolvemos el error exacto
        return pd.DataFrame(), str(e)

df, error_msg = cargar_datos_maestros()

# --- DIAGNÓSTICO EN PANTALLA ---
if df.empty:
    st.error(f"🚨 Fallo de conexión o tabla vacía. El error real es: {error_msg}")
    st.stop()
elif 'Upside Potencial' not in df.columns:
    st.error("⚠️ La conexión fue exitosa pero la columna tiene un nombre inesperado.")
    st.warning(f"🔍 Las columnas que Streamlit está viendo son: {df.columns.tolist()}")
    st.stop()

# ==========================================
# 2. BARRA LATERAL: LOGIN Y FILTROS
# ==========================================
st.sidebar.title("🔐 Acceso")

if st.session_state['usuario_id'] is None:
    tab_login, tab_registro = st.sidebar.tabs(["Ingresar", "Registrarse"])
    
    with tab_login:
        user_login = st.text_input("Usuario", key="log_user")
        pass_login = st.text_input("Contraseña", type="password", key="log_pass")
        if st.button("Entrar"):
            c = conn.cursor()
            c.execute(text("SELECT id FROM usuarios WHERE username=? AND password=?"), (user_login, hash_password(pass_login)))
            resultado = c.fetchone()
            if resultado:
                st.session_state['usuario_id'] = resultado[0]
                st.session_state['username'] = user_login
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")
                
    with tab_registro:
        user_reg = st.text_input("Nuevo Usuario", key="reg_user")
        pass_reg = st.text_input("Nueva Contraseña", type="password", key="reg_pass")
        if st.button("Crear Cuenta"):
            try:
                c = conn.cursor()
                c.execute(text("INSERT INTO usuarios (username, password) VALUES (?, ?)"), (user_reg, hash_password(pass_reg)))
                conn.commit()
                st.success("¡Cuenta creada! Ya puedes ingresar.")
            except sqlite3.IntegrityError:
                st.error("Ese nombre de usuario ya existe.")
else:
    st.sidebar.success(f"Hola, **{st.session_state['username']}** 👋")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['usuario_id'] = None
        st.session_state['username'] = None
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("🔍 Configuración del Radar")
if 'Ultima Actualizacion' in df.columns:
    st.sidebar.info(f"📅 Datos del: **{df['Ultima Actualizacion'].iloc[0]}**")

min_upside = st.sidebar.slider("Upside Mínimo (%)", 0, 100, 10)
ticker_buscar = st.sidebar.text_input("Buscar Ticker o Empresa", "").upper()

# --- SELECTORES ---
lista_sectores = ["Todos"] + sorted(df['Sector'].dropna().unique().tolist()) if 'Sector' in df.columns else ["Todos"]
sector_buscar = st.sidebar.selectbox("🏢 Filtrar por Sector", lista_sectores)

lista_decisiones = ["Todas"] + sorted(df['Decisión'].dropna().unique().tolist()) if 'Decisión' in df.columns else ["Todas"]
decision_buscar = st.sidebar.selectbox("⚖️ Filtrar por Decisión", lista_decisiones)

# ==========================================
# 3. MOTOR DE FILTROS EN CASCADA Y KPIs
# ==========================================
# Filtramos solo para las pestañas de Radar (el Portafolio usará el df completo)
df_radar = df[df['Upside Potencial'] > (min_upside/100)].copy()

if ticker_buscar:
    df_radar = df_radar[df_radar['Ticker'].str.contains(ticker_buscar) | df_radar['Empresa'].str.upper().str.contains(ticker_buscar)]
if sector_buscar != "Todos":
    df_radar = df_radar[df_radar['Sector'] == sector_buscar]
if decision_buscar != "Todas":
    df_radar = df_radar[df_radar['Decisión'] == decision_buscar]

# Cálculo Global de Salud Financiera para TODO el DataFrame
if 'Activo Circulante' in df.columns:
    pas_circ = df['Pasivo Circulante'].replace(0, 1).fillna(1)
    act_tot = df['Activo Total'].replace(0, 1).fillna(1)
    ventas = df['Ventas Totales'].replace(0, 1).fillna(1)
    gastos_int = df['Gastos por Intereses'].replace(0, 1).fillna(1)

    pa = (df['Activo Circulante'].fillna(0) - df['Inventario'].fillna(0)) / pas_circ
    rc = df['Activo Circulante'].fillna(0) / pas_circ
    end = df['Pasivo Total'].fillna(0) / act_tot
    mn = df['Utilidad Neta'].fillna(0) / ventas
    ci = df['EBIT'].fillna(0) / gastos_int

    df['Todo_Verde'] = (pa >= 1) & (rc >= 1.5) & (end < 0.50) & (mn > 0.10) & (ci > 3)
    df['Salud Financiera'] = df['Todo_Verde'].apply(lambda x: '🟢 Impecable' if x else '🟡 Con Riesgos')
    
    # Sincronizamos el df_radar con los nuevos cálculos
    df_radar = df.loc[df_radar.index].copy()
else:
    df['Todo_Verde'] = False
    df['Salud Financiera'] = 'Pendiente...'
    df_radar['Salud Financiera'] = 'Pendiente...'

# ==========================================
# 4. INTERFAZ PRINCIPAL (PESTAÑAS)
# ==========================================
st.title("🎯 El Radar de Valor Democratizado")
st.markdown("**Objetivo:** Encontrar empresas sólidas del S&P 500 que cotizan por debajo de su valor real.")

# --- NUEVA PESTAÑA: MI PORTAFOLIO ---
tab1, tab2, tab3 = st.tabs(["📉 Radar de Oportunidades", "🛡️ Estrategia de Portafolio", "💼 Mi Portafolio (Alertas)"])

# ------------------------------------------
# PESTAÑA 1: RADAR Y CAJA DE CRISTAL
# ------------------------------------------
with tab1:
    st.subheader(f"🏆 Oportunidades Detectadas ({len(df_radar)})")
    
    if not df_radar.empty:
        cols_mostrar = ['Ticker', 'Empresa', 'Sector', 'Precio', 'Valor Justo', 'Upside Potencial', 'Decisión', 'Salud Financiera']
        st.dataframe(
            df_radar[cols_mostrar].style.format({"Precio": "${:.2f}", "Valor Justo": "${:.2f}", "Upside Potencial": "{:.1%}"}),
            use_container_width=True
        )

        # --- CAJA DE CRISTAL ---
        st.markdown("---")
        st.header("💎 Caja de Cristal: Auditoría")
        
        df_radar['Etiqueta_Selector'] = df_radar['Ticker'] + " - " + df_radar['Empresa']
        seleccion_etiqueta = st.selectbox("Selecciona empresa a auditar:", sorted(df_radar['Etiqueta_Selector'].tolist()))

        if seleccion_etiqueta:
            ticker_sel = seleccion_etiqueta.split(" - ")[0]
            dato = df_radar[df_radar['Ticker'] == ticker_sel].iloc[0]

            st.subheader(f"Auditoría de: {dato['Empresa']}")
            
            c4, c5, c6 = st.columns(3)
            c4.metric("Flujo de Caja (FCF)", f"${dato.get('FCF', 0):,.0f}")
            c5.metric("Crecimiento (g)", f"{dato.get('Crecimiento (g)', 0):.1%}")
            c6.metric("Riesgo (WACC)", f"{dato.get('WACC', 0):.1%}")
            
            with st.expander("🔍 Ver origen matemático de FCF, g y WACC"):
                st.latex(r"WACC = (W_e \times K_e) + (W_d \times K_d \times (1 - t))")
                st.info(f"**WACC Final:** {dato.get('WACC', 0):.1%}")
            
            # Veredicto
            st.divider()
            st.subheader("🎯 Veredicto Final")
            k1, k2, k3 = st.columns(3)
            k1.metric("Precio Actual", f"${dato['Precio']:.2f}")
            k2.metric("Valor Justo", f"${dato['Valor Justo']:.2f}")
            k3.metric("Upside Potencial", f"{dato['Upside Potencial']:.1%}", delta=dato['Decisión'])
    else:
        st.warning("🕵️‍♂️ No se encontró ninguna empresa que cumpla con los filtros.")

# ------------------------------------------
# PESTAÑA 2: ESTRATEGIA
# ------------------------------------------
with tab2:
    st.header("🛡️ Gestión de Riesgo y Sectores")
    if not df_radar.empty and 'Sector' in df_radar.columns:
        fig = px.pie(df_radar, names='Sector', title='Distribución por Sector', hole=0.4)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay datos suficientes para graficar.")

# ------------------------------------------
# PESTAÑA 3: MI PORTAFOLIO (SEGUIMIENTO)
# ------------------------------------------
with tab3:
    st.header("💼 Seguimiento de Portafolio")
    
    if st.session_state['usuario_id'] is None:
        st.warning("🔒 **Inicia sesión o regístrate en la barra lateral para crear tu portafolio.**")
        st.write("Aquí podrás agregar las empresas en las que ya invertiste. El radar vigilará su precio todos los días y te avisará con una alerta roja cuando alcancen su Valor Justo para que puedas tomar ganancias.")
    else:
        usuario_id = st.session_state['usuario_id']
        
        # 1. Formulario para agregar Ticker
        st.subheader("➕ Agregar Empresa")
        col_t, col_b = st.columns([3, 1])
        with col_t:
            # Lista de todos los tickers en la base maestra
            todos_los_tickers = sorted(df['Ticker'].unique().tolist())
            ticker_nuevo = st.selectbox("Selecciona el Ticker:", [""] + todos_los_tickers)
        with col_b:
            st.write("") # Espaciador
            st.write("")
            if st.button("Guardar en Portafolio", use_container_width=True):
                if ticker_nuevo:
                    # Validar que no esté repetido
                    c = conn.cursor()
                    c.execute(text("SELECT id FROM portafolios WHERE usuario_id=? AND ticker=?"), (usuario_id, ticker_nuevo))
                    if not c.fetchone():
                        c.execute(text("INSERT INTO portafolios (usuario_id, ticker) VALUES (?, ?)"), (usuario_id, ticker_nuevo))
                        conn.commit()
                        st.success(f"{ticker_nuevo} agregado.")
                        st.rerun()
                    else:
                        st.warning("Esa empresa ya está en tu portafolio.")
                        
        st.markdown("---")
        
        # 2. Mostrar la tabla del Portafolio Personal
        st.subheader("📊 Mis Posiciones Actuales")
        
        # Consultamos los tickers guardados por el usuario
        df_mis_tickers = pd.read_sql(f"SELECT ticker FROM portafolios WHERE usuario_id={usuario_id}", conn)
        
        if not df_mis_tickers.empty:
            lista_mis_tickers = df_mis_tickers['ticker'].tolist()
            
            # Cruzamos los tickers del usuario con la tabla maestra completa
            mi_portafolio = df[df['Ticker'].isin(lista_mis_tickers)].copy()
            
            # Función para resaltar si es hora de vender
            def colorear_alertas(row):
                if row['Decisión'] == 'MANTENER/VENTA':
                    return ['background-color: #8B0000; color: white'] * len(row) # Rojo oscuro
                return [''] * len(row)
                
            cols_portafolio = ['Ticker', 'Empresa', 'Precio', 'Valor Justo', 'Upside Potencial', 'Decisión', 'Salud Financiera']
            
            st.dataframe(
                mi_portafolio[cols_portafolio].style.apply(colorear_alertas, axis=1).format({
                    "Precio": "${:.2f}",
                    "Valor Justo": "${:.2f}",
                    "Upside Potencial": "{:.1%}"
                }),
                use_container_width=True
            )
            
            # Botón para limpiar portafolio
            if st.button("🗑️ Eliminar empresa seleccionada"):
                st.info("💡 Tip: Para eliminar, puedes conectar un botón de borrado SQL más adelante, o borrar el archivo `.db` para reiniciar el entorno de pruebas.")
        else:
            st.info("Aún no tienes empresas en seguimiento. Selecciona una en el menú de arriba.")

# Cerramos conexión al final
conn.close()
