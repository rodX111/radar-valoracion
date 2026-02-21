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

# --- NUEVO: SELECTOR DE SECTOR ---
if 'Sector' in df.columns:
    # Creamos una lista alfabética de sectores y le agregamos "Todos" al inicio
    lista_sectores = ["Todos"] + sorted(df['Sector'].dropna().unique().tolist())
    sector_buscar = st.sidebar.selectbox("🏢 Filtrar por Sector", lista_sectores)
else:
    sector_buscar = "Todos"

# ==========================================
# APLICAR FILTROS EN CASCADA
# ==========================================
# 1. Filtro de ganancia mínima
df_filtrado = df[df['Upside Potencial'] > (min_upside/100)]

# 2. Filtro de búsqueda por texto (Ticker)
if ticker_buscar:
    df_filtrado = df_filtrado[
        df_filtrado['Ticker'].str.contains(ticker_buscar) | 
        df_filtrado['Empresa'].str.upper().str.contains(ticker_buscar)
    ]

# 3. Filtro por Industria/Sector
if sector_buscar != "Todos":
    df_filtrado = df_filtrado[df_filtrado['Sector'] == sector_buscar]

# ==========================================
# ESCUDO ANTI-CRASH
# ==========================================
if df_filtrado.empty:
    st.warning("🕵️‍♂️ No se encontró ninguna empresa que cumpla con todos estos filtros.")
    st.info("💡 Intenta bajar el 'Upside Mínimo' o asegúrate de que el Ticker pertenezca al Sector que seleccionaste.")
    st.stop() 

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
    lista_empresas = sorted(df_filtrado['Etiqueta_Selector'].tolist())
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
        act_circ = dato.get('Activo Circulante', 0)
        inv = dato.get('Inventario', 0)
        pas_circ = dato.get('Pasivo Circulante', 1) 
        act_tot = dato.get('Activo Total', 1)
        pas_tot = dato.get('Pasivo Total', 0)
        util_neta = dato.get('Utilidad Neta', 0)
        ventas = dato.get('Ventas Totales', 1)
        ebit = dato.get('EBIT', 0) 
        gastos_int = dato.get('Gastos por Intereses', 1) 

        # 1. PRUEBA ÁCIDA
        st.markdown("##### 🧪 1. Prueba Ácida")
        st.write("Mide la capacidad de pagar deudas a corto plazo sin depender de vender el inventario.")
        st.markdown("**Fórmula:** (Activo Circulante - Inventarios) / Pasivos circulantes")
        prueba_acida = (act_circ - inv) / pas_circ
        texto_pa = f"**Cálculo:** ({act_circ:,.0f} - {inv:,.0f}) / {pas_circ:,.0f} = **{prueba_acida:.2f}**"
        
        if prueba_acida >= 1:
            st.success(texto_pa + " ✅ (Buena liquidez)")
        else:
            st.error(texto_pa + " 🚨 (Riesgo de liquidez a corto plazo)")

        # 2. RAZÓN CIRCULANTE (LIQUIDEZ)
        st.markdown("##### 💧 2. Razón Circulante")
        st.write("Indica si la empresa tiene suficientes activos a corto plazo para cubrir sus deudas a corto plazo.")
        st.markdown("**Fórmula:** Activo Circulante / Pasivo Circulante")
        razon_circulante = act_circ / pas_circ
        texto_rc = f"**Cálculo:** {act_circ:,.0f} / {pas_circ:,.0f} = **{razon_circulante:.2f}**"
        
        if razon_circulante >= 1.5:
            st.success(texto_rc + " ✅ (Liquidez holgada)")
        elif razon_circulante >= 1:
            st.warning(texto_rc + " ⚠️ (Liquidez justa)")
        else:
            st.error(texto_rc + " 🚨 (Falta de liquidez)")

        # 3. RAZÓN DE ENDEUDAMIENTO
        st.markdown("##### ⚖️ 3. Razón de Endeudamiento")
        st.write("Mide qué porcentaje de los activos totales de la empresa está financiado por deuda.")
        st.markdown("**Fórmula:** Pasivo Total / Activo Total")
        endeudamiento = pas_tot / act_tot
        texto_end = f"**Cálculo:** {pas_tot:,.0f} / {act_tot:,.0f} = **{endeudamiento:.1%}**" # Formateado como porcentaje
        
        if endeudamiento < 0.50:
            st.success(texto_end + " ✅ (Sano, menor al 50%)")
        else:
            st.warning(texto_end + " ⚠️ (Alto endeudamiento, mayor al 50%)")

        # 4. MARGEN DE UTILIDAD NETA
        st.markdown("##### 💵 4. Margen de Utilidad Neta")
        st.write("Mide cuánto de cada dólar en ventas se convierte en ganancia real.")
        st.markdown("**Fórmula:** (Utilidad Neta / Ventas Totales) * 100")
        margen_neto = (util_neta / ventas)
        texto_mn = f"**Cálculo:** ({util_neta:,.0f} / {ventas:,.0f}) * 100 = **{margen_neto:.2%}**"
        
        if margen_neto > 0.10: # Si gana más del 10% limpio, es excelente
            st.success(texto_mn + " ✅ (Buen margen)")
        elif margen_neto > 0:
            st.warning(texto_mn + " ⚠️ (Margen estrecho)")
        else:
            st.error(texto_mn + " 🚨 (La empresa está perdiendo dinero)")

        # 5. COBERTURA DE INTERESES
        st.markdown("##### 🛡️ 5. Cobertura de Intereses")
        st.write("Mide cuántas veces la empresa puede pagar sus gastos por intereses con su utilidad operativa.")
        st.markdown("**Fórmula:** Utilidad Operativa (EBIT) / Gastos por Intereses")
        cobertura_int = ebit / gastos_int
        texto_ci = f"**Cálculo:** {ebit:,.0f} / {gastos_int:,.0f} = **{cobertura_int:.2f}x**"
        
        if cobertura_int > 3:
            st.success(texto_ci + " ✅ (Cobertura segura, mayor a 3x)")
        elif cobertura_int > 1.5:
            st.warning(texto_ci + " ⚠️ (Cobertura ajustada)")
        else:
            st.error(texto_ci + " 🚨 (Peligro de impago, menor a 1.5x)")

# ==============================================================================
# PESTAÑA 2: ESTRATEGIA DE PORTAFOLIO 
# ==============================================================================
with tab2:
    st.header("🛡️ Gestión de Riesgo y Sectores")
    
    # Validamos que ya existan los datos contables en el CSV
    if 'Sector' in df_filtrado.columns and 'Activo Circulante' in df_filtrado.columns:
        
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
            if not df_filtrado.empty:
                top_sector = df_filtrado['Sector'].value_counts().idxmax()
                st.write(f"⚠️ Tu mayor exposición actual es a: **{top_sector}**")

        st.markdown("---")
        
        # 2. LAS MEJORES DE CADA CLASE (FILTRO DE CALIDAD ESTRICTO)
        st.subheader("💎 Las Mejores de Cada Sector (Filtro de Calidad)")
        st.write("Seleccionamos la opción con **mayor Upside** de cada industria, priorizando aquellas que tienen **salud financiera perfecta** (Todo en Verde).")
        
        # --- CÁLCULO MASIVO DE KPIs (Vectorizado para ser ultra rápido) ---
        # Usamos .replace(0, 1) para evitar divisiones matemáticas por cero
        pas_circ_seguro = df_filtrado['Pasivo Circulante'].replace(0, 1).fillna(1)
        act_tot_seguro = df_filtrado['Activo Total'].replace(0, 1).fillna(1)
        ventas_seguro = df_filtrado['Ventas Totales'].replace(0, 1).fillna(1)
        gastos_int_seguro = df_filtrado['Gastos por Intereses'].replace(0, 1).fillna(1)

        pa = (df_filtrado['Activo Circulante'].fillna(0) - df_filtrado['Inventario'].fillna(0)) / pas_circ_seguro
        rc = df_filtrado['Activo Circulante'].fillna(0) / pas_circ_seguro
        end = df_filtrado['Pasivo Total'].fillna(0) / act_tot_seguro
        mn = df_filtrado['Utilidad Neta'].fillna(0) / ventas_seguro
        ci = df_filtrado['EBIT'].fillna(0) / gastos_int_seguro

        # Evaluamos las 5 reglas de oro para que sea "Todo Verde"
        df_filtrado['Todo_Verde'] = (pa >= 1) & (rc >= 1.5) & (end < 0.50) & (mn > 0.10) & (ci > 3)

        # --- SELECCIÓN INTELIGENTE POR SECTOR ---
        mejores_lista = []
        sectores = df_filtrado['Sector'].unique()
        
        for s in sectores:
            df_sector = df_filtrado[df_filtrado['Sector'] == s]
            
            # Filtramos solo las que son "Todo Verde"
            df_verdes = df_sector[df_sector['Todo_Verde'] == True]
            
            if not df_verdes.empty:
                # Si hay empresas perfectas en este sector, tomamos la de mayor Upside
                mejor = df_verdes.loc[df_verdes['Upside Potencial'].idxmax()].copy()
                mejor['Salud Financiera'] = '🟢 Impecable'
            else:
                # Si NINGUNA empresa de este sector pasó todas las pruebas, 
                # tomamos la de mayor Upside general, pero le ponemos la etiqueta de alerta.
                mejor = df_sector.loc[df_sector['Upside Potencial'].idxmax()].copy()
                mejor['Salud Financiera'] = '🟡 Con Riesgos'
            
            mejores_lista.append(mejor)
            
        mejores_sector = pd.DataFrame(mejores_lista)
        
        # --- MOSTRAR LA TABLA CON FORMATO ---
        cols_finales = ['Sector', 'Ticker', 'Empresa', 'Precio', 'Upside Potencial', 'Salud Financiera']
        
        # Función para pintar las filas
        def colorear_filas(row):
            if row['Salud Financiera'] == '🟡 Con Riesgos':
                return ['background-color: #4d4d00; color: white'] * len(row) # Fondo oscuro amarillo/oliva (amigable con modo oscuro/claro)
            elif row['Salud Financiera'] == '🟢 Impecable':
                return ['background-color: #003311; color: white'] * len(row) # Fondo verde oscuro
            return [''] * len(row)

        st.dataframe(
            mejores_sector[cols_finales].style.apply(colorear_filas, axis=1).format({
                "Precio": "${:.2f}",
                "Upside Potencial": "{:.1%}"
            }),
            use_container_width=True
        )
        
    else:
        st.info("⚠️ Aún no se han cargado los datos contables completos. Espera a la próxima actualización del robot.")






