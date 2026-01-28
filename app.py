import streamlit as st
import pandas as pd

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Radar de Valoración - Rodrigo",
    page_icon="🎯",
    layout="wide"
)

# --- TÍTULO Y DESCRIPCIÓN ---
st.title("🎯 El Radar de Valor de Rodrigo")
st.markdown("""
**Bienvenido inversor.** Esta herramienta analiza automáticamente las acciones del S&P 500 para encontrar empresas que el mercado ha castigado injustamente.
* **Criterio:** Usamos Flujos de Caja Descontados (DCF) conservadores.
* **Objetivo:** Encontrar acciones que valen más de lo que cuestan hoy.
""")

# --- BARRA LATERAL (FILTROS) ---
st.sidebar.header("🔍 Filtra tus Oportunidades")
min_upside = st.sidebar.slider("Potencial de Subida Mínimo (%)", 0, 100, 20)
sector_seleccion = st.sidebar.text_input("Buscar por Ticker (ej. MO)", "")

# --- CARGAR DATOS ---
@st.cache_data # Esto hace que la web sea súper rápida
def cargar_datos():
    # Leemos el CSV que generó tu script
    df = pd.read_csv("resultados_valoracion_filtrados.csv")
    return df

try:
    df = cargar_datos()
    
    # --- FILTRADO EN TIEMPO REAL ---
    # Convertimos el upside a porcentaje numérico para filtrar (ej. 0.20)
    filtro_upside = min_upside / 100
    
    df_filtrado = df[df['Upside Potencial'] > filtro_upside]
    
    if sector_seleccion:
        df_filtrado = df_filtrado[df_filtrado['Ticker'].str.contains(sector_seleccion.upper())]

    # --- MÉTRICAS PRINCIPALES ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Empresas Analizadas", "500+")
    col2.metric("Oportunidades Detectadas", len(df))
    col3.metric("Top Pick del Día", df.iloc[0]['Ticker'], f"+{df.iloc[0]['Upside Potencial']:.1%}")

    # --- TABLA INTERACTIVA ---
    st.subheader(f"🏆 Top Oportunidades (Upside > {min_upside}%)")
    
    # Formato bonito para los números
    st.dataframe(
        df_filtrado.style.format({
            "Precio": "${:.2f}",
            "Valor Justo": "${:.2f}",
            "Precio Max Compra": "${:.2f}",
            "Upside Potencial": "{:.1%}",
            "WACC": "{:.1%}"
        }),
        height=500
    )

    # --- DESCARGO DE RESPONSABILIDAD ---
    st.warning("⚠️ **Disclaimer:** Esta herramienta es solo para fines educativos. No constituye asesoramiento financiero profesional. Realiza siempre tu propia investigación.")

except FileNotFoundError:
    st.error("⚠️ No se encontró el archivo 'resultados_valoracion_filtrados.csv'. Asegúrate de que esté en la misma carpeta que este script.")