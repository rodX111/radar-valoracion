import streamlit as st
import pandas as pd

st.set_page_config(page_title="Radar de Valor", page_icon="🎯", layout="wide")

# --- TÍTULO ---
st.title("🎯 El Radar de Valor Democratizado")
st.markdown("**Objetivo:** Encontrar empresas sólidas del S&P 500 que cotizan por debajo de su valor real.")

# --- CARGAR DATOS ---
@st.cache_data
def cargar_datos():
    try:
        return pd.read_csv("resultados_valoracion_filtrados.csv")
    except:
        return pd.DataFrame()

df = cargar_datos()

if df.empty:
    st.error("⚠️ Aún no hay datos. Espera a que el robot termine de ejecutarse.")
    st.stop()

# --- FILTROS ---
st.sidebar.header("🔍 Filtros")
min_upside = st.sidebar.slider("Upside Mínimo (%)", 0, 100, 10)
ticker_buscar = st.sidebar.text_input("Buscar Ticker", "").upper()

df_filtrado = df[df['Upside Potencial'] > (min_upside/100)]
if ticker_buscar:
    df_filtrado = df_filtrado[df_filtrado['Ticker'].str.contains(ticker_buscar)]

# --- TABLA PRINCIPAL ---
st.subheader(f"🏆 Oportunidades Detectadas ({len(df_filtrado)})")
st.dataframe(
    df_filtrado[['Ticker', 'Precio', 'Valor Justo', 'Upside Potencial', 'Decisión', 'WACC']].style.format({
        "Precio": "${:.2f}",
        "Valor Justo": "${:.2f}",
        "Upside Potencial": "{:.1%}",
        "WACC": "{:.1%}"
    })
)

# --- 💎 SECCIÓN CAJA DE CRISTAL (NUEVO) ---
st.markdown("---")
st.header("💎 Caja de Cristal: ¿Por qué vale eso?")
st.info("Selecciona una empresa para ver el desglose matemático paso a paso. Pasa el mouse por los signos '?' para ver las fórmulas.")

# Selector de empresa
lista_empresas = df_filtrado['Ticker'].tolist()
seleccion = st.selectbox("Selecciona empresa a auditar:", lista_empresas)

if seleccion:
    # Obtener datos de la fila seleccionada
    dato = df_filtrado[df_filtrado['Ticker'] == seleccion].iloc[0]

    # PASO 1: DEUDA
    st.subheader("1️⃣ Paso 1: Deuda Real (Enterprise Value)")
    col1, col2, col3 = st.columns(3)
    
    col1.metric("Deuda Total", f"${dato['Deuda Total']:,.0f}", help="Dinero total que debe la empresa a bancos y acreedores.")
    col2.metric("(-) Total Cash", f"${dato['Total Cash']:,.0f}", help="Efectivo disponible en caja.")
    col3.metric("(=) Deuda Neta", f"${dato['Deuda Neta']:,.0f}", delta="Pasivo Real", delta_color="inverse",
                help=f"Fórmula: {dato['Deuda Total']:,.0f} - {dato['Total Cash']:,.0f}")
    
    st.write("---")
    
    # PASO 2: VALOR TOTAL
    colA, colB, colC = st.columns(3)
    colA.metric("Market Cap", f"${dato['Market Cap']:,.0f}", help="Precio Acción x Número de Acciones.")
    colB.metric("(+) Deuda Neta", f"${dato['Deuda Neta']:,.0f}", help="La deuda que asume el comprador.")
    colC.metric("(=) Enterprise Value", f"${dato['Enterprise Value']:,.0f}", 
                help=f"Lo que cuesta comprar la empresa entera. Fórmula: Market Cap + Deuda Neta")

    st.write("---")

    # PASO 3: WACC Y FLUJO
    st.subheader("2️⃣ Paso 2: La Fórmula Maestra")
    st.latex(r"Valor = \frac{FCF \times (1 + g)}{WACC - g}")
    
    colX, colY, colZ = st.columns(3)
    colX.metric("Flujo de Caja (FCF)", f"${dato['FCF']:,.0f}", help="Dinero libre que genera el negocio tras pagar gastos e inversiones.")
    colY.metric("Crecimiento (g)", f"{dato['Crecimiento (g)']:.1%}", help="Cuánto esperamos que crezca la empresa anualmente.")
    colZ.metric("Riesgo (WACC)", f"{dato['WACC']:.1%}", help="Costo del capital. Si el retorno es menor a esto, destruye valor.")

    st.success(f"📌 **Conclusión:** Según estos datos, **{seleccion}** debería valer **${dato['Valor Justo']:.2f}**. Como cotiza a **${dato['Precio']:.2f}**, tiene un potencial de **{dato['Upside Potencial']:.1%}**.")
