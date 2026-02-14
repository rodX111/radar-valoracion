import streamlit as st
import pandas as pd
import plotly.express as px

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Radar de Valor", page_icon="🎯", layout="wide")

# --- TÍTULO PRINCIPAL ---
st.title("🎯 El Radar de Valor de Rodrigo")
st.markdown("**Objetivo:** Encontrar empresas sólidas del S&P 500 que cotizan por debajo de su valor real.")

# --- CARGAR DATOS ---
@st.cache_data(ttl=3600)
def cargar_datos():
    try:
        return pd.read_csv("resultados_valoracion_filtrados.csv")
    except:
        return pd.DataFrame()

df = cargar_datos()

if df.empty:
    st.error("⚠️ Aún no hay datos. Espera a que el robot termine de ejecutarse.")
    st.stop()

# --- BARRA LATERAL (FILTROS GLOBALES) ---
st.sidebar.header("🔍 Configuración")
if 'Ultima Actualizacion' in df.columns:
    st.sidebar.info(f"📅 Datos del: **{df['Ultima Actualizacion'].iloc[0]}**")

min_upside = st.sidebar.slider("Upside Mínimo (%)", 0, 100, 10)
ticker_buscar = st.sidebar.text_input("Buscar Ticker o Empresa", "").upper()

# Aplicar filtros
df_filtrado = df[df['Upside Potencial'] > (min_upside/100)]

if ticker_buscar:
    df_filtrado = df_filtrado[
        df_filtrado['Ticker'].str.contains(ticker_buscar) | 
        df_filtrado['Empresa'].str.upper().str.contains(ticker_buscar)
    ]

# --- CREACIÓN DE PESTAÑAS ---
tab1, tab2 = st.tabs(["📉 Radar de Oportunidades", "🛡️ Estrategia de Portafolio"])

# ==============================================================================
# PESTAÑA 1: RADAR DE VALOR (TABLA + CAJA DE CRISTAL)
# ==============================================================================
with tab1:
    st.subheader(f"🏆 Oportunidades Detectadas ({len(df_filtrado)})")

    # Columnas a mostrar
    cols_mostrar = ['Ticker', 'Empresa', 'Sector', 'Precio', 'Valor Justo', 'Upside Potencial', 'Decisión']
    
    # Validación por si el CSV aún no tiene la columna Sector
    if 'Sector' not in df_filtrado.columns:
        df_filtrado['Sector'] = "Pendiente..."

    st.dataframe(
        df_filtrado[cols_mostrar].style.format({
            "Precio": "${:.2f}",
            "Valor Justo": "${:.2f}",
            "Upside Potencial": "{:.1%}"
        }),
        use_container_width=True
    )

    # --- CAJA DE CRISTAL ---
    st.markdown("---")
    st.header("💎 Caja de Cristal: Auditoría")
    st.info("Selecciona una empresa para ver el desglose matemático paso a paso.")

    # Selector inteligente
    df_filtrado['Etiqueta_Selector'] = df_filtrado['Ticker'] + " - " + df_filtrado['Empresa']
    lista_empresas = df_filtrado['Etiqueta_Selector'].tolist()
    seleccion_etiqueta = st.selectbox("Selecciona empresa a auditar:", lista_empresas)

    if seleccion_etiqueta:
        ticker_seleccionado = seleccion_etiqueta.split(" - ")[0]
        dato = df_filtrado[df_filtrado['Ticker'] == ticker_seleccionado].iloc[0]

        st.subheader(f"Auditoría de: {dato['Empresa']} ({dato['Ticker']})")

        # PASO 1
        st.markdown("##### 1️⃣ Paso 1: Deuda Real (Enterprise Value)")
        c1, c2, c3 = st.columns(3)
        c1.metric("Deuda Total", f"${dato['Deuda Total']:,.0f}", help="Deuda con bancos.")
        c2.metric("(-) Total Cash", f"${dato['Total Cash']:,.0f}", help="Efectivo en caja.")
        c3.metric("(=) Deuda Neta", f"${dato['Deuda Neta']:,.0f}", delta="Pasivo Real", delta_color="inverse")

        st.divider()

        # PASO 2
        st.markdown("##### 2️⃣ Paso 2: La Fórmula Maestra")
        st.latex(r"Valor = \frac{FCF \times (1 + g)}{WACC - g}")
        
        c4, c5, c6 = st.columns(3)
        c4.metric("Flujo de Caja (FCF)", f"${dato['FCF']:,.0f}")
        c5.metric("Crecimiento (g)", f"{dato['Crecimiento (g)']:.1%}")
        c6.metric("Riesgo (WACC)", f"{dato['WACC']:.1%}")

        st.divider()

        # CONCLUSIÓN
        st.subheader("🎯 Veredicto Final")
        precio_max = dato.get('Precio Max Compra', dato['Valor Justo'] * 0.8)
        
        k1, k2, k3 = st.columns(3)
        k1.metric("Valor Justo", f"${dato['Valor Justo']:.2f}")
        k2.metric("Margen Seguridad", "20%")
        k3.metric("Precio MÁXIMO Compra", f"${precio_max:.2f}", delta="Tu Límite", delta_color="normal")

# ==============================================================================
# PESTAÑA 2: ESTRATEGIA DE PORTAFOLIO (NUEVO)
# ==============================================================================
with tab2:
    st.header("🛡️ Gestión de Riesgo y Sectores")
    
    if 'Sector' in df_filtrado.columns:
        # 1. GRÁFICO DE SECTORES
        col_pie, col_info = st.columns([2, 1])
        
        with col_pie:
            fig = px.pie(df_filtrado, names='Sector', title='Distribución de Oportunidades por Sector', hole=0.4)
            fig.update_traces(textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
        
        with col_info:
            st.warning("💡 **Tip de Inversión:**")
            st.write("No compres todas las acciones del mismo color. Si el sector **Tecnología** cae, querrás tener algo en **Consumo Defensivo** o **Salud** para compensar.")
            
            # Conteo
            top_sector = df_filtrado['Sector'].value_counts().idxmax()
            st.write(f"⚠️ Tu mayor exposición actual es a: **{top_sector}**")

        st.markdown("---")
        
        # 2. LAS MEJORES DE CADA CLASE (BEST IN CLASS)
        st.subheader("💎 Las Mejores de Cada Sector")
        st.write("Si quieres diversificar, aquí tienes la opción más barata (mayor Upside) de cada industria disponible:")
        
        # Agrupamos por sector y sacamos la que tiene mayor Upside
        mejores_sector = df_filtrado.loc[df_filtrado.groupby("Sector")["Upside Potencial"].idxmax()]
        
        st.dataframe(
            mejores_sector[['Sector', 'Ticker', 'Empresa', 'Precio', 'Upside Potencial']].style.format({
                "Precio": "${:.2f}",
                "Upside Potencial": "{:.1%}"
            }),
            use_container_width=True
        )
        
    else:
        st.info("⚠️ Aún no se han cargado los datos de Sectores. Espera a la próxima actualización del robot.")
