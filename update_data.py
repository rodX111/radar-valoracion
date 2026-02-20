import yfinance as yf
import pandas as pd
import requests
import numpy as np
from datetime import date
import time  # <--- NUEVO: Librería para controlar el tiempo

# ==========================================
# 1. CONFIGURACIÓN Y CONSTANTES
# ==========================================
TASA_LIBRE_RIESGO = 0.042  # 4.2% (Bono a 10 años USA)
PRIMA_RIESGO_MERCADO = 0.05  # 5.0%
TASA_CRECIMIENTO_TERMINAL = 0.025  # 2.5%
MARGEN_SEGURIDAD = 0.20  # 20%

# Headers para evitar bloqueo de Wikipedia
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# ==========================================
# 2. OBTENER UNIVERSO DE EMPRESAS (S&P 1500)
# ==========================================
def obtener_todos_los_tickers():
    tickers = []
    
    # El "disfraz" para que Wikipedia nos deje entrar
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        print("📡 Descargando lista S&P 500 (Gigantes)...")
        res_500 = requests.get('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies', headers=HEADERS)
        sp500 = pd.read_html(res_500.text)[0]
        tickers.extend(sp500['Symbol'].tolist())
        
        print("📡 Descargando lista S&P 400 (Medianas)...")
        res_400 = requests.get('https://en.wikipedia.org/wiki/List_of_S%26P_400_companies', headers=HEADERS)
        sp400 = pd.read_html(res_400.text)[0]
        tickers.extend(sp400['Symbol'].tolist())

        print("📡 Descargando lista S&P 600 (Pequeñas)...")
        res_600 = requests.get('https://en.wikipedia.org/wiki/List_of_S%26P_600_companies', headers=HEADERS)
        sp600 = pd.read_html(res_600.text)[0]
        tickers.extend(sp600['Symbol'].tolist())
        
        # Limpieza: Reemplazar puntos por guiones (BRK.B -> BRK-B) y eliminar duplicados
        tickers = [t.replace('.', '-') for t in tickers]
        tickers = list(set(tickers)) # Eliminar duplicados
        
        print(f"✅ Total de empresas a analizar: {len(tickers)}")
        return tickers

    except Exception as e:
        print(f"⚠️ Error descargando listas: {e}")
        return []

# ==========================================
# 3. MOTOR DE VALORACIÓN (Con Blindaje)
# ==========================================
def valorar_empresa(ticker_symbol):
    try:
        # Descarga de datos
        empresa = yf.Ticker(ticker_symbol)
        info = empresa.info
        
        # --- FILTRO 1: DATOS CRÍTICOS FALTANTES ---
        # Si no hay precio o Market Cap, abortamos misión con esta empresa.
        if 'currentPrice' not in info or 'marketCap' not in info:
            return None

        # --- DATOS GENERALES ---
        nombre_oficial = info.get('longName', ticker_symbol)
        sector = info.get('sector', 'Desconocido') # Capturamos Sector
        
        precio_actual = info['currentPrice']
        market_cap = info['marketCap']
        beta = info.get('beta', 1.0)
        
        # --- DATOS FINANCIEROS (Con valores por defecto si fallan) ---
        deuda_total = info.get('totalDebt', 0)
        if deuda_total is None: deuda_total = 0
            
        total_cash = info.get('totalCash', 0)
        if total_cash is None: total_cash = 0
            
        ebitda = info.get('ebitda', 0)
        shares_outstanding = info.get('sharesOutstanding', 0)
        
        # Flujo de Caja Libre (FCF)
        fcf = info.get('freeCashflow')
        if fcf is None:
            # Plan B: Calcularlo manualmente si Yahoo no lo da directo
            operating_cashflow = info.get('operatingCashflow', 0)
            capex = info.get('capitalExpenditures', 0) # Suele venir negativo
            if operating_cashflow and capex:
                fcf = operating_cashflow + capex # Se suma porque capex es negativo
            else:
                return None # Si no hay datos de flujo, no podemos valorar

        # --- CÁLCULOS ---
        deuda_neta = deuda_total - total_cash
        enterprise_value = market_cap + deuda_neta
        
        # Costo del Capital (Ke) - CAPM
        ke = TASA_LIBRE_RIESGO + (beta * PRIMA_RIESGO_MERCADO)
        
        # Costo de la Deuda (Kd) - Estimado
        gastos_intereses = info.get('interestExpense', 0) # Suele ser negativo
        if gastos_intereses is None: gastos_intereses = 0
            
        if deuda_total > 0 and gastos_intereses != 0:
            kd = abs(gastos_intereses) / deuda_total
        else:
            kd = 0.05 # Estimado conservador del 5% si no hay datos
            
        tax_rate = 0.21 
        kd_neto = kd * (1 - tax_rate)
        
        # WACC
        peso_e = market_cap / enterprise_value
        peso_d = deuda_neta / enterprise_value if enterprise_value > 0 else 0
        wacc = (peso_e * ke) + (peso_d * kd_neto)
        
        if wacc <= 0.04: wacc = 0.04 # Suelo mínimo por seguridad
        if wacc > 0.15: wacc = 0.15  # Techo máximo para no castigar excesivamente

        # Tasa de Crecimiento (g)
        # Usamos las estimaciones de analistas si existen, si no, conservador
        estimado_crecimiento = info.get('earningsGrowth', 0.03)
        g = min(estimado_crecimiento, 0.03) # Topeamos al 3% para ser conservadores (Value Investing)

        # VALORACIÓN (Gordon Growth Model modificado)
        # Valor = FCF * (1+g) / (WACC - g)
        if (wacc - g) <= 0:
            return None # Matemáticamente imposible

        valor_empresa_total = (fcf * (1 + g)) / (wacc - g)
        valor_equity = valor_empresa_total - deuda_neta
        
        if shares_outstanding > 0:
            valor_intrinseco = valor_equity / shares_outstanding
        else:
            return None

        # --- FILTRO DE CALIDAD ---
        if valor_intrinseco <= 0: return None # No queremos empresas quebradas

        # RESULTADOS
        precio_compra_max = valor_intrinseco * (1 - MARGEN_SEGURIDAD)
        decision = "COMPRA FUERTE" if precio_actual < precio_compra_max else "MANTENER/VENTA"
        upside = (valor_intrinseco - precio_actual) / precio_actual

        return {
            "Ticker": ticker_symbol,
            "Empresa": nombre_oficial,
            "Sector": sector,
            "Precio": precio_actual,
            "Valor Justo": valor_intrinseco,
            "Precio Max Compra": precio_compra_max,
            "Upside Potencial": upside,
            "Decisión": decision,
            "WACC": wacc,
            "Deuda Total": deuda_total,
            "Total Cash": total_cash,
            "Deuda Neta": deuda_neta,
            "Market Cap": market_cap,
            "Enterprise Value": enterprise_value,
            "FCF": fcf,
            "Crecimiento (g)": g,
            "Ke": ke,
            "Kd": kd,
            "Beta": beta
        }

    except Exception as e:
        # Si falla cualquier cosa rara, simplemente devolvemos None y el loop sigue
        return None

# ==========================================
# 4. EJECUCIÓN PRINCIPAL
# ==========================================
if __name__ == "__main__":
    tickers = obtener_todos_los_tickers()
    
    if not tickers:
        print("❌ No se pudieron obtener tickers. Abortando.")
        exit()
        
    resultados = []
    total = len(tickers)
    
    print(f"🚀 Iniciando análisis de {total} empresas del S&P 1500...")
    
for i, ticker in enumerate(tickers):
        print(f"[{i+1}/{total}] Analizando {ticker}...", end="\r") 
        
        datos = valorar_empresa(ticker)
        if datos:
            resultados.append(datos)
            
        # --- NUEVA PAUSA ARTIFICIAL (ANTI-BLOQUEOS) ---
        time.sleep(0.5) 
            
print("\n✅ Análisis completado.")
    
df_final = pd.DataFrame(resultados)

# Filtros de Calidad y Guardado
if not df_final.empty:
    # Filtramos basura: WACC lógico y Upside no infinito
    df_final = df_final[df_final['WACC'] >= 0.04] 
    df_final = df_final[df_final['Upside Potencial'] <= 3.0] # Descartar errores de >300% upside (suelen ser fallos de datos)
    df_final = df_final[df_final['Upside Potencial'] > 0]
        
    # Agregamos Fecha
    df_final['Ultima Actualizacion'] = date.today().strftime('%d/%m/%Y')
        
    # Guardamos
    df_final.to_csv('resultados_valoracion_filtrados.csv', index=False)
    print(f"💾 Guardado: {len(df_final)} oportunidades encontradas.")
else:
    print("⚠️ No se encontraron oportunidades que cumplan los criterios.")



