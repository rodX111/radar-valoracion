import streamlit as st
import pandas as pd
import plotly.express as px

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Radar de Valor", page_icon="🎯", layout="wide")

# --- TÍTULO PRINCIPAL ---
st.title("🎯 El Radar de Valor Democratizado")
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

        # ==========================================
        # NUEVA SECCIÓN: RAZONES FINANCIERAS (KPIs)
        # ==========================================
        st.divider()
        st.subheader("📚 KPIs y Razones Financieras")
        st.write("Evaluación de la salud de la empresa paso a paso:")

        # --- Extracción segura de datos ---
        # (Si el dato no existe aún en el CSV, usamos 0 o 1 para evitar errores matemáticos)
        act_circ = dato.get('Activo Circulante', 0)
        inv = dato.get('Inventario', 0)
        pas_circ = dato.get('Pasivo Circulante', 1) # 1 para no dividir por cero
        act_tot = dato.get('Activo Total', 1)
        pas_tot = dato.get('Pasivo Total', 0)
        util_neta = dato.get('Utilidad Neta', 0)
        ventas = dato.get('Ventas Totales', 1)

        # 1. PRUEBA ÁCIDA
        st.markdown("##### 🧪 1. Prueba Ácida")
        st.write("Mide la capacidad de pagar deudas a corto plazo sin depender de vender el inventario.")
        st.markdown("**Fórmula:** Prueba ácida = (Activo Circulante - Inventarios) / Pasivos circulantes")
        prueba_acida = (act_circ - inv) / pas_circ
        st.info(f"**Cálculo:** ({act_circ:,.0f} - {inv:,.0f}) / {pas_circ:,.0f} = **{prueba_acida:.2f}**")

        # 2. RAZÓN CIRCULANTE (LIQUIDEZ)
        st.markdown("##### 💧 2. Razón Circulante")
        st.write("Indica si la empresa tiene suficientes activos a corto plazo para cubrir sus deudas a corto plazo.")
        st.markdown("**Fórmula:** Razón Circulante = Activo Circulante / Pasivo Circulante")
        razon_circulante = act_circ / pas_circ
        st.info(f"**Cálculo:** {act_circ:,.0f} / {pas_circ:,.0f} = **{razon_circulante:.2f}**")

        # 3. RAZÓN DE ENDEUDAMIENTO
        st.markdown("##### ⚖️ 3. Razón de Endeudamiento")
        st.write("Mide qué porcentaje de los activos totales de la empresa está financiado por deuda.")
        st.markdown("**Fórmula:** Endeudamiento = Pasivo Total / Activo Total")
        endeudamiento = pas_tot / act_tot
        st.info(f"**Cálculo:** {pas_tot:,.0f} / {act_tot:,.0f} = **{endeudamiento:.2f}**")

        # 4. MARGEN DE UTILIDAD NETA
        st.markdown("##### 💵 4. Margen de Utilidad Neta")
        st.write("Mide cuánto de cada dólar en ventas se convierte en ganancia real.")
        st.markdown("**Fórmula:** Margen Neto = (Utilidad Neta / Ventas Totales) * 100")
        margen_neto = (util_neta / ventas) * 100
        st.info(f"**Cálculo:** ({util_neta:,.0f} / {ventas:,.0f}) * 100 = **{margen_neto:.2f}%**")

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


