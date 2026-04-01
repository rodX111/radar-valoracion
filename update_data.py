import yfinance as yf
import pandas as pd
import requests
import numpy as np
from datetime import date
import time
from sqlalchemy import create_engine # <--- NUEVO

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
# 3. MOTOR DE VALORACIÓN (Con KPIs Contables)
# ==========================================
def valorar_empresa(ticker_symbol):
    try:
        empresa = yf.Ticker(ticker_symbol)
        info = empresa.info
        
        # Filtro de seguridad inicial
        if 'currentPrice' not in info or 'marketCap' not in info:
            return None

        # --- DATOS GENERALES ---
        nombre_oficial = info.get('longName', ticker_symbol)
        sector = info.get('sector', 'Desconocido')
        precio_actual = info['currentPrice']
        market_cap = info['marketCap']
        beta = info.get('beta', 1.0)
        
        # --- DESCARGA DE ESTADOS FINANCIEROS ---
        balance = empresa.balance_sheet
        resultados = empresa.financials
        
        # Función auxiliar para buscar métricas de forma segura en los reportes
        def obtener_metrica(df, nombres_posibles):
            if df is None or df.empty: 
                return 0
            for nombre in nombres_posibles:
                if nombre in df.index:
                    # Toma el dato de la primera columna (el año más reciente reportado)
                    dato = df.loc[nombre].iloc[0]
                    # Si es NaN (vacío), devolvemos 0
                    return dato if not pd.isna(dato) else 0
            return 0

        # --- EXTRACCIÓN DE NUEVOS KPIs CONTABLES ---
        act_circ = obtener_metrica(balance, ['Current Assets', 'Total Current Assets'])
        inv = obtener_metrica(balance, ['Inventory'])
        pas_circ = obtener_metrica(balance, ['Current Liabilities', 'Total Current Liabilities'])
        act_tot = obtener_metrica(balance, ['Total Assets'])
        pas_tot = obtener_metrica(balance, ['Total Liabilities Net Minority Interest', 'Total Liabilities'])
        
        util_neta = obtener_metrica(resultados, ['Net Income', 'Net Income Common Stockholders'])
        ventas = obtener_metrica(resultados, ['Total Revenue', 'Operating Revenue'])
        ebit = obtener_metrica(resultados, ['EBIT', 'Operating Income'])
        gastos_int = obtener_metrica(resultados, ['Interest Expense', 'Interest Expense Non Operating'])
        # A veces los gastos por intereses vienen en negativo, nos aseguramos de usar el valor absoluto:
        gastos_int = abs(gastos_int) if gastos_int != 0 else 1 # 1 para evitar división por cero luego

        # --- DATOS FINANCIEROS (Para Valoración) ---
        deuda_total = info.get('totalDebt', 0)
        if deuda_total is None: deuda_total = 0
            
        total_cash = info.get('totalCash', 0)
        if total_cash is None: total_cash = 0
        
        shares_outstanding = info.get('sharesOutstanding', 0)
        
        # Flujo de Caja Libre (FCF)
        fcf = info.get('freeCashflow')
        if fcf is None:
            operating_cashflow = info.get('operatingCashflow', 0)
            capex = info.get('capitalExpenditures', 0)
            if operating_cashflow and capex:
                fcf = operating_cashflow + capex
            else:
                return None

        # --- CÁLCULOS WACC Y DCF ---
        deuda_neta = deuda_total - total_cash
        enterprise_value = market_cap + deuda_neta
        
        ke = TASA_LIBRE_RIESGO + (beta * PRIMA_RIESGO_MERCADO)
        kd = gastos_int / deuda_total if deuda_total > 0 else 0.05
        kd_neto = kd * (1 - 0.21)
        
        peso_e = market_cap / enterprise_value if enterprise_value > 0 else 1
        peso_d = deuda_neta / enterprise_value if enterprise_value > 0 else 0
        wacc = (peso_e * ke) + (peso_d * kd_neto)
        
        if wacc <= 0.04: wacc = 0.04
        if wacc > 0.15: wacc = 0.15

        g = min(info.get('earningsGrowth', 0.03), 0.03)

        if (wacc - g) <= 0: return None

        valor_empresa_total = (fcf * (1 + g)) / (wacc - g)
        valor_equity = valor_empresa_total - deuda_neta
        
        if shares_outstanding > 0:
            valor_intrinseco = valor_equity / shares_outstanding
        else:
            return None

        if valor_intrinseco <= 0: return None

        precio_compra_max = valor_intrinseco * (1 - MARGEN_SEGURIDAD)
        decision = "COMPRA FUERTE" if precio_actual < precio_compra_max else "MANTENER/VENTA"
        upside = (valor_intrinseco - precio_actual) / precio_actual

        # RESULTADOS CON LAS NUEVAS VARIABLES
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
            "FCF": fcf,
            "Crecimiento (g)": g,
            "Deuda Total": deuda_total,
            "Total Cash": total_cash,
            "Deuda Neta": deuda_neta,
            # --- NUEVOS CAMPOS CONTABLES ---
            "Activo Circulante": act_circ,
            "Inventario": inv,
            "Pasivo Circulante": pas_circ,
            "Activo Total": act_tot,
            "Pasivo Total": pas_tot,
            "Utilidad Neta": util_neta,
            "Ventas Totales": ventas,
            "EBIT": ebit,
            "Gastos por Intereses": gastos_int,
            # --- NUEVOS CAMPOS WACC ---
            "Beta": beta,
            "Ke": ke,
            "Kd Neto": kd_neto,
            "Peso Equity": peso_e,
            "Peso Deuda": peso_d
        }

    except Exception as e:
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
    
for i, ticker in enumerate(tickers[:5]):
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
    df_final = df_final[df_final['WACC'] >= 0.04] 
    df_final = df_final[df_final['Upside Potencial'] <= 3.0] 
    df_final['Ultima Actualizacion'] = date.today().strftime('%d/%m/%Y')
        
    print("💾 Conectando a Supabase (PostgreSQL)...")
    # Pon tu URL real de Supabase aquí para el robot
    URL_SUPABASE = "postgresql://postgres:Guate%402021xyz@db.mayauvnugqgxgffxvdgi.supabase.co:5432/postgres"
    
    motor = create_engine(URL_SUPABASE)
    
    # Mandamos los datos a la nube
    df_final.to_sql('acciones_maestro', motor, if_exists='replace', index=False)
    
    print(f"✅ Base de datos en la nube actualizada: {len(df_final)} empresas guardadas.")
else:
    print("⚠️ No se encontraron oportunidades.")
