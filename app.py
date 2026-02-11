import streamlit as st
import pandas as pd

st.set_page_config(page_title="Radar de Valor", page_icon="🎯", layout="wide")

# --- TÍTULO ---
st.title("🎯 El Radar de Valor Democratizado")
st.markdown("**Objetivo:** Encontrar empresas sólidas del S&P 500 que cotizan por debajo de su valor real.")

# --- CARGAR DATOS ---

@st.cache_data(ttl=3600) # Recuerda el ttl para que refresque cada hora
def cargar_datos():
    try:
        return pd.read_csv("resultados_valoracion_filtrados.csv")
    except:
        return pd.DataFrame()

df = cargar_datos()

if df.empty:
    st.error("⚠️ Aún no hay datos.")
    st.stop()

# --- MOSTRAR FECHA DE ACTUALIZACIÓN (NUEVO) ---
# Leemos la fecha de la primera fila (ya que todas tienen la misma)
if 'Ultima Actualizacion' in df.columns:
    fecha_data = df['Ultima Actualizacion'].iloc[0]
    st.info(f"📅 **Datos actualizados al:** {fecha_data}")
else:
    st.warning("⚠️ Fecha no disponible (esperando próxima actualización del robot).")
    
# --- FILTROS ---
st.sidebar.header("🔍 Filtros")
min_upside = st.sidebar.slider("Upside Mínimo (%)", 0, 100, 10)
ticker_buscar = st.sidebar.text_input("Buscar Ticker o Empresa", "").upper()

df_filtrado = df[df['Upside Potencial'] > (min_upside/100)]

if ticker_buscar:
    # Ahora buscamos tanto en el Ticker como en el Nombre de la Empresa
    df_filtrado = df_filtrado[
        df_filtrado['Ticker'].str.contains(ticker_buscar) | 
        df_filtrado['Empresa'].str.upper().str.contains(ticker_buscar)
    ]

# --- TABLA PRINCIPAL ---
st.subheader(f"🏆 Oportunidades Detectadas ({len(df_filtrado)})")

# Reordenamos las columnas para poner el Nombre al principio
cols_mostrar = ['Ticker', 'Empresa', 'Precio', 'Valor Justo', 'Upside Potencial', 'Decisión', 'WACC']

# Verificamos si la columna 'Empresa' existe (por si el CSV viejo aún no se actualizó)
if 'Empresa' not in df_filtrado.columns:
    df_filtrado['Empresa'] = df_filtrado['Ticker'] # Parche temporal

st.dataframe(
    df_filtrado[cols_mostrar].style.format({
        "Precio": "${:.2f}",
        "Valor Justo": "${:.2f}",
        "Upside Potencial": "{:.1%}",
        "WACC": "{:.1%}"
    }),
    use_container_width=True
)

# --- 💎 SECCIÓN CAJA DE CRISTAL ---
st.markdown("---")
st.header("💎 Caja de Cristal: ¿Por qué vale eso?")
st.info("Selecciona una empresa para ver el desglose matemático paso a paso.")

# Creamos una lista bonita "KO - The Coca-Cola Company" para el selector
df_filtrado['Etiqueta_Selector'] = df_filtrado['Ticker'] + " - " + df_filtrado['Empresa']
lista_empresas = df_filtrado['Etiqueta_Selector'].tolist()

seleccion_etiqueta = st.selectbox("Selecciona empresa a auditar:", lista_empresas)

if seleccion_etiqueta:
    # Recuperamos el Ticker original separando el texto
    ticker_seleccionado = seleccion_etiqueta.split(" - ")[0]
    
    # Obtener datos usando el Ticker
    dato = df_filtrado[df_filtrado['Ticker'] == ticker_seleccionado].iloc[0]

    st.subheader(f"Auditoría de: {dato['Empresa']} ({dato['Ticker']})")

    # PASO 1: DEUDA
    st.markdown("##### 1️⃣ Paso 1: Deuda Real (Enterprise Value)")
    col1, col2, col3 = st.columns(3)
    
    col1.metric("Deuda Total", f"${dato['Deuda Total']:,.0f}", help="Dinero total que debe la empresa.")
    col2.metric("(-) Total Cash", f"${dato['Total Cash']:,.0f}", help="Efectivo disponible en caja.")
    col3.metric("(=) Deuda Neta", f"${dato['Deuda Neta']:,.0f}", delta="Pasivo Real", delta_color="inverse",
                help=f"Fórmula: {dato['Deuda Total']:,.0f} - {dato['Total Cash']:,.0f}")
    
    st.divider()
    
    # PASO 2: VALOR TOTAL
    colA, colB, colC = st.columns(3)
    colA.metric("Market Cap", f"${dato['Market Cap']:,.0f}", help="Precio Acción x Número de Acciones.")
    colB.metric("(+) Deuda Neta", f"${dato['Deuda Neta']:,.0f}", help="La deuda que asume el comprador.")
    colC.metric("(=) Enterprise Value", f"${dato['Enterprise Value']:,.0f}", 
                help="Lo que cuesta comprar la empresa entera. (Market Cap + Deuda Neta)")

    st.divider()

    # PASO 3: WACC Y FLUJO
    st.markdown("##### 2️⃣ Paso 2: La Fórmula Maestra")
    st.latex(r"Valor = \frac{FCF \times (1 + g)}{WACC - g}")
    
    colX, colY, colZ = st.columns(3)
    colX.metric("Flujo de Caja (FCF)", f"${dato['FCF']:,.0f}", help="Dinero libre que genera el negocio.")
    colY.metric("Crecimiento (g)", f"{dato['Crecimiento (g)']:.1%}", help="Crecimiento anual estimado.")
    colZ.metric("Riesgo (WACC)", f"{dato['WACC']:.1%}", help="Costo del capital.")

# ... (código anterior de FCF, g, WACC) ...

    st.divider()

    # --- CONCLUSIÓN FINAL CON MARGEN DE SEGURIDAD ---
    st.subheader("🎯 Veredicto Final")
    
    # Recuperamos el Precio Max Compra (si existe, si no lo calculamos al vuelo por seguridad)
    precio_max = dato.get('Precio Max Compra', dato['Valor Justo'] * 0.8)

    col_final1, col_final2, col_final3 = st.columns(3)

    col_final1.metric("Valor Justo (Teórico)", f"${dato['Valor Justo']:.2f}", 
                      help="Lo que vale la empresa si tus estimaciones son perfectas.")

    col_final2.metric("Margen de Seguridad", "20%", 
                      help="Descuento que exigimos por si nos equivocamos en los cálculos.")

    col_final3.metric("Precio MÁXIMO de Compra", f"${precio_max:.2f}", 
                      delta="Tu Precio Límite",
                      help="No pagues ni un centavo más de esto.")

    # Mensaje de decisión
    if dato['Precio'] < precio_max:
        st.success(f"✅ **¡LUZ VERDE!** La acción cotiza a **${dato['Precio']:.2f}**, que está por debajo de tu precio límite de **${precio_max:.2f}**. Es una oportunidad de compra con margen de seguridad.")
    else:
        st.warning(f"⚠️ **PRECAUCIÓN:** La acción cotiza a **${dato['Precio']:.2f}**. Aunque vale **${dato['Valor Justo']:.2f}**, no tienes suficiente margen de seguridad (necesitas que baje a **${precio_max:.2f}**).")



