import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine, text, exc
import hashlib

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Radar de Valor", page_icon="🎯", layout="wide")

# ==========================================
# 1. MOTOR DE BASE DE DATOS Y USUARIOS (NUBE)
# ==========================================
DB_URL = st.secrets["DB_URL"]
motor = create_engine(DB_URL)

def init_db():
    with motor.connect() as conn:
        conn.execute(text('''CREATE TABLE IF NOT EXISTS usuarios 
                     (id SERIAL PRIMARY KEY, username TEXT UNIQUE, password TEXT)'''))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS portafolios 
                     (id SERIAL PRIMARY KEY, usuario_id INTEGER, ticker TEXT, 
                     FOREIGN KEY(usuario_id) REFERENCES usuarios(id))'''))
        conn.commit()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

init_db()

if 'usuario_id' not in st.session_state:
    st.session_state['usuario_id'] = None
    st.session_state['username'] = None

# --- CARGAR DATOS DEL ROBOT ---
@st.cache_data(ttl=600)
def cargar_datos_maestros():
    try:
        url_secreta = st.secrets["DB_URL"]
        df = pd.read_sql("SELECT * FROM acciones_maestro", con=url_secreta)
        return df, None
    except Exception as e:
        return pd.DataFrame(), str(e)

df, error_msg = cargar_datos_maestros()

if df.empty:
    st.error(f"🚨 Fallo al leer los datos. El error es: {error_msg}")
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
            with motor.connect() as conn:
                resultado = conn.execute(
                    text("SELECT id FROM usuarios WHERE username=:u AND password=:p"), 
                    {"u": user_login, "p": hash_password(pass_login)}
                ).fetchone()
                
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
                with motor.connect() as conn:
                    conn.execute(
                        text("INSERT INTO usuarios (username, password) VALUES (:u, :p)"), 
                        {"u": user_reg, "p": hash_password(pass_reg)}
                    )
                    conn.commit()
                    st.success("¡Cuenta creada! Ya puedes ingresar.")
            except exc.IntegrityError:
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
# 3. MOTOR DE FILTROS Y KPIs DE SALUD
# ==========================================
df_radar = df[df['Upside Potencial'] > (min_upside/100)].copy()

if ticker_buscar:
    df_radar = df_radar[df_radar['Ticker'].str.contains(ticker_buscar) | df_radar['Empresa'].str.upper().str.contains(ticker_buscar)]
if sector_buscar != "Todos":
    df_radar = df_radar[df_radar['Sector'] == sector_buscar]
if decision_buscar != "Todas":
    df_radar = df_radar[df_radar['Decisión'] == decision_buscar]

# Cálculo de Salud Financiera
if 'Activo Circulante' in df.columns:
    pas_circ = df['Pasivo Circulante'].replace(0, 1).fillna(1)
    act_tot = df['Activo Total'].replace(0, 1).fillna(1)
    ventas = df['Ventas Totales'].replace(0, 1).fillna(1)
    gastos_int = df['Gastos por Intereses'].replace(0, 1).fillna(1)

    df['PA'] = (df['Activo Circulante'].fillna(0) - df['Inventario'].fillna(0)) / pas_circ
    df['RC'] = df['Activo Circulante'].fillna(0) / pas_circ
    df['END'] = df['Pasivo Total'].fillna(0) / act_tot
    df['MN'] = df['Utilidad Neta'].fillna(0) / ventas
    df['CI'] = df['EBIT'].fillna(0) / gastos_int

    df['Todo_Verde'] = (df['PA'] >= 1) & (df['RC'] >= 1.5) & (df['END'] < 0.50) & (df['MN'] > 0.10) & (df['CI'] > 3)
    df['Salud Financiera'] = df['Todo_Verde'].apply(lambda x: '🟢 Impecable' if x else '🟡 Con Riesgos')
    
    df_radar = df.loc[df_radar.index].copy()
else:
    df['Salud Financiera'] = 'Pendiente...'

# ==========================================
# 4. INTERFAZ PRINCIPAL
# ==========================================
st.title("🎯 El Radar de Valor Democratizado")
st.markdown("**Objetivo:** Encontrar empresas sólidas del S&P 500 que cotizan por debajo de su valor real.")

tab1, tab2, tab3 = st.tabs(["📉 Radar de Oportunidades", "🛡️ Estrategia de Portafolio", "💼 Mi Portafolio (Alertas)"])

# PESTAÑA 1: RADAR Y CAJA DE CRISTAL
with tab1:
    st.subheader(f"🏆 Oportunidades Detectadas ({len(df_radar)})")
    
    if not df_radar.empty:
        cols_mostrar = ['Ticker', 'Empresa', 'Sector', 'Precio', 'Valor Justo', 'Upside Potencial', 'Decisión', 'Salud Financiera']
        st.dataframe(
            df_radar[cols_mostrar].style.format({"Precio": "${:.2f}", "Valor Justo": "${:.2f}", "Upside Potencial": "{:.1%}"}),
            use_container_width=True
        )

        st.markdown("---")
        st.header("💎 Caja de Cristal: Auditoría")
        
        df_radar['Etiqueta_Selector'] = df_radar['Ticker'] + " - " + df_radar['Empresa']
        seleccion_etiqueta = st.selectbox("Selecciona empresa a auditar:", sorted(df_radar['Etiqueta_Selector'].tolist()))

        if seleccion_etiqueta:
            ticker_sel = seleccion_etiqueta.split(" - ")[0]
            dato = df_radar[df_radar['Ticker'] == ticker_sel].iloc[0]

            st.subheader(f"Auditoría de: {dato['Empresa']}")
            
            # --- SECCIÓN 1: COMPONENTES DE VALORACIÓN ---
            st.write("#### 1. Variables del Modelo DCF")
            c1, c2, c3 = st.columns(3)
            c1.metric("Flujo de Caja (FCF)", f"${dato.get('FCF', 0):,.0f}")
            c2.metric("Crecimiento (g)", f"{dato.get('Crecimiento (g)', 0):.1%}")
            c3.metric("Riesgo (WACC)", f"{dato.get('WACC', 0):.1%}")

            # --- NUEVA SECCIÓN: DESGLOSE MATEMÁTICO ---
# --- NUEVA SECCIÓN: DESGLOSE MATEMÁTICO ---
            with st.expander("🧮 Ver desglose matemático exacto (Paso a Paso)", expanded=False):
                # Extracción de variables
                wacc = dato.get('WACC', 0)
                g = dato.get('Crecimiento (g)', 0)
                fcf = dato.get('FCF', 0)
                peso_e = dato.get('Peso Equity', 0)
                ke = dato.get('Ke', 0)
                peso_d = dato.get('Peso Deuda', 0)
                kd = dato.get('Kd Neto', 0)
                total_cash = dato.get('Total Cash', 0)
                deuda_total = dato.get('Deuda Total', 0)
                valor_justo = dato.get('Valor Justo', 0)
                
                # Reconstrucción matemática en vivo
                ev = (fcf * (1 + g)) / (wacc - g) if (wacc - g) > 0 else 0
                equity_value = ev + total_cash - deuda_total
                acciones = equity_value / valor_justo if valor_justo > 0 else 0
                
                st.markdown("**Paso 1: Tasa de Descuento (WACC)**")
                st.latex(r"WACC = (W_e \times K_e) + (W_d \times K_d \text{ Neto})")
                st.latex(rf"WACC = ({peso_e*100:.1f}\%) \times ({ke*100:.1f}\%) + ({peso_d*100:.1f}\%) \times ({kd*100:.1f}\%) = {wacc*100:.1f}\%")
                
                st.markdown("**Paso 2: Valor de la Empresa (Enterprise Value)**")
                st.latex(r"EV = \frac{FCF \times (1 + g)}{WACC - g}")
                st.latex(rf"EV = \frac{{\${fcf:,.0f} \times (1 + {g*100:.1f}\%)}}{{{wacc*100:.1f}\% - {g*100:.1f}\%}} = \${ev:,.0f}")
                
                st.markdown("**Paso 3: Valor para el Accionista (Equity Value)**")
                st.latex(r"Equity = EV + Total Cash - Deuda Total")
                st.latex(rf"Equity = \${ev:,.0f} + \${total_cash:,.0f} - \${deuda_total:,.0f} = \${equity_value:,.0f}")
                
                st.markdown("**Paso 4: Valor Justo por Acción**")
                st.latex(r"Valor Justo = \frac{Equity Value}{Acciones \text{ en } Circulación}")
                st.latex(rf"Valor Justo = \frac{{\${equity_value:,.0f}}}{{{acciones:,.0f} \text{{ acciones estimadas}}}} = \${valor_justo:.2f}")

            # --- SECCIÓN 2: RIESGO Y SALUD ---
            with st.expander("🛡️ Análisis de Riesgo y Salud Financiera", expanded=True):
                col_salud, col_desc = st.columns([1, 3])
                col_salud.metric("Estado General", dato['Salud Financiera'])
                col_desc.info("Los indicadores a continuación validan si la empresa tiene la solidez necesaria para sobrevivir a largo plazo.")
                
                st.write("##### Razones Financieras Clave")
                r1, r2, r3, r4, r5 = st.columns(5)
                r1.metric("Prueba Ácida", f"{dato.get('PA', 0):.2f}", help="Ideal > 1.0")
                r2.metric("Razón Circulante", f"{dato.get('RC', 0):.2f}", help="Ideal > 1.5")
                r3.metric("Endeudamiento", f"{dato.get('END', 0):.1%}", help="Ideal < 50%")
                r4.metric("Cobertura Int.", f"{dato.get('CI', 0):.1f}x", help="Ideal > 3.0")
                r5.metric("Margen Neto", f"{dato.get('MN', 0):.1%}", help="Ideal > 10%")

                # --- DESGLOSE MATEMÁTICO DE SALUD FINANCIERA ---
                st.markdown("---")
                st.write("##### 🧮 Desglose Matemático")
                
                # Extracción de variables crudas
                act_circ = dato.get('Activo Circulante', 0)
                inv = dato.get('Inventario', 0)
                pas_circ = dato.get('Pasivo Circulante', 0)
                pas_tot = dato.get('Pasivo Total', 0)
                act_tot = dato.get('Activo Total', 0)
                ebit = dato.get('EBIT', 0)
                gastos_int = dato.get('Gastos por Intereses', 0)
                util_neta = dato.get('Utilidad Neta', 0)
                ventas = dato.get('Ventas Totales', 0)

                # Dividimos las 5 fórmulas en dos columnas para aprovechar el espacio
                c_math1, c_math2 = st.columns(2)
                
                with c_math1:
                    st.markdown("**1. Prueba Ácida (Liquidez Inmediata)**")
                    st.latex(r"Prueba\ \acute{A}cida = \frac{Activo\ Circulante - Inventario}{Pasivo\ Circulante}")
                    st.latex(rf"PA = \frac{{\${act_circ:,.0f} - \${inv:,.0f}}}{{\${pas_circ:,.0f}}} = {dato.get('PA', 0):.2f}")
                    
                    st.markdown("**2. Razón Circulante (Liquidez a Corto Plazo)**")
                    st.latex(r"Raz\acute{o}n\ Circulante = \frac{Activo\ Circulante}{Pasivo\ Circulante}")
                    st.latex(rf"RC = \frac{{\${act_circ:,.0f}}}{{\${pas_circ:,.0f}}} = {dato.get('RC', 0):.2f}")
                    
                    st.markdown("**3. Endeudamiento (Solvencia)**")
                    st.latex(r"Endeudamiento = \frac{Pasivo\ Total}{Activo\ Total}")
                    st.latex(rf"END = \frac{{\${pas_tot:,.0f}}}{{\${act_tot:,.0f}}} = {dato.get('END', 0)*100:.1f}\%")

                with c_math2:
                    st.markdown("**4. Cobertura de Intereses (Capacidad de Pago)**")
                    st.latex(r"Cobertura\ Int. = \frac{EBIT}{Gastos\ por\ Intereses}")
                    st.latex(rf"CI = \frac{{\${ebit:,.0f}}}{{\${gastos_int:,.0f}}} = {dato.get('CI', 0):.1f}x")
                    
                    st.markdown("**5. Margen Neto (Rentabilidad)**")
                    st.latex(r"Margen\ Neto = \frac{Utilidad\ Neta}{Ventas\ Totales}")
                    st.latex(rf"MN = \frac{{\${util_neta:,.0f}}}{{\${ventas:,.0f}}} = {dato.get('MN', 0)*100:.1f}\%")

            # --- SECCIÓN 3: VEREDICTO FINAL ---
            st.divider()
            st.subheader("🎯 Veredicto Final")
            v1, v2, v3 = st.columns(3)
            v1.metric("Precio Actual", f"${dato['Precio']:.2f}")
            v2.metric("Valor Justo", f"${dato['Valor Justo']:.2f}")
            v3.metric("Upside Potencial", f"{dato['Upside Potencial']:.1%}", delta=dato['Decisión'])
    else:
        st.warning("🕵️‍♂️ No se encontró ninguna empresa que cumpla con los filtros.")

# PESTAÑA 2: ESTRATEGIA
with tab2:
    st.header("🛡️ Gestión de Riesgo y Calidad")
    st.subheader("🏆 El Top 10 Absoluto")
    df_top10 = df_radar[df_radar['Todo_Verde'] == True].nlargest(10, 'Upside Potencial')
    if not df_top10.empty:
        st.dataframe(df_top10[['Ticker', 'Empresa', 'Upside Potencial', 'Salud Financiera']].style.format({"Upside Potencial": "{:.1%}"}), use_container_width=True)
    
    if not df_radar.empty and 'Sector' in df_radar.columns:
        fig = px.pie(df_radar, names='Sector', title='Distribución de Oportunidades por Sector', hole=0.4)
        st.plotly_chart(fig, use_container_width=True)

# PESTAÑA 3: MI PORTAFOLIO
with tab3:
    st.header("💼 Seguimiento de Portafolio")
    
    if st.session_state['usuario_id'] is None:
        st.warning("🔒 Inicia sesión para crear tu portafolio.")
    else:
        usuario_id = st.session_state['usuario_id']
        st.subheader("➕ Agregar Empresa")
        todos_los_tickers = sorted(df['Ticker'].unique().tolist())
        ticker_nuevo = st.selectbox("Selecciona el Ticker:", [""] + todos_los_tickers)
        
        if st.button("Guardar en Portafolio"):
            if ticker_nuevo:
                with motor.connect() as conn:
                    existe = conn.execute(text("SELECT id FROM portafolios WHERE usuario_id=:uid AND ticker=:t"), {"uid": usuario_id, "t": ticker_nuevo}).fetchone()
                    if not existe:
                        conn.execute(text("INSERT INTO portafolios (usuario_id, ticker) VALUES (:uid, :t)"), {"uid": usuario_id, "t": ticker_nuevo})
                        conn.commit()
                        st.success(f"{ticker_nuevo} agregado.")
                        st.rerun()
        
        st.markdown("---")
        df_mis_tickers = pd.read_sql(text("SELECT ticker FROM portafolios WHERE usuario_id=:uid"), motor, params={"uid": usuario_id})
        
        if not df_mis_tickers.empty:
            mi_portafolio = df[df['Ticker'].isin(df_mis_tickers['ticker'].tolist())].copy()
            st.dataframe(mi_portafolio[['Ticker', 'Empresa', 'Precio', 'Valor Justo', 'Upside Potencial', 'Decisión']].style.format({"Precio": "${:.2f}", "Valor Justo": "${:.2f}", "Upside Potencial": "{:.1%}"}), use_container_width=True)
