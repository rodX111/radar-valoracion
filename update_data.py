import yfinance as yf
import pandas as pd
import requests
import numpy as np

# --- CONFIGURACIÓN ---
MARKET_RETURN = 0.08
GROWTH_CAP = 0.03
MARGEN_SEGURIDAD = 0.20

# Tasa libre de riesgo
try:
    tnx = yf.Ticker("^TNX")
    RISK_FREE_RATE = tnx.history(period="1d")['Close'].iloc[-1] / 100
except:
    RISK_FREE_RATE = 0.042

def valorar_empresa(ticker_symbol):
    try:
        empresa = yf.Ticker(ticker_symbol)
        info = empresa.info
        
        if 'currentPrice' not in info or 'marketCap' not in info:
            return None

        nombre_oficial = info.get('longName', ticker_symbol) # Si no encuentra nombre, usa el Ticker
        precio_actual = info['currentPrice']
        market_cap = info['marketCap']
        beta = info.get('beta', 1.0)

        balance = empresa.balance_sheet
        resultados = empresa.financials
        flujo = empresa.cashflow
        
        if balance.empty or resultados.empty or flujo.empty:
            return None

        # 1. DEUDA
        try:
            deuda_total = balance.loc['Total Debt'].iloc[0]
        except KeyError:
            try:
                deuda_total = balance.loc['Total Debt And Capital Lease Obligation'].iloc[0]
            except KeyError:
                deuda_total = 0

        total_cash = info.get("totalCash", 0)
        deuda_neta = deuda_total - total_cash
        enterprise_value = market_cap + deuda_neta
        
        if enterprise_value <= 0: return None

        # 2. WACC
        ke = RISK_FREE_RATE + beta * (MARKET_RETURN - RISK_FREE_RATE)
        
        try:
            interest_expense = abs(resultados.loc['Interest Expense'].iloc[0])
            tax_provision = resultados.loc['Tax Provision'].iloc[0]
            pretax_income = resultados.loc['Pretax Income'].iloc[0]
            tax_rate = tax_provision / pretax_income if pretax_income != 0 else 0.21
            if tax_rate < 0 or tax_rate > 0.5: tax_rate = 0.21
            
            costo_deuda_bruto = interest_expense / deuda_total if deuda_total > 0 else 0
            kd = costo_deuda_bruto * (1 - tax_rate)
        except:
            kd = 0.04

        w_e = market_cap / enterprise_value
        w_d = deuda_neta / enterprise_value
        wacc = (w_e * ke) + (w_d * kd)
        
        # 3. CRECIMIENTO Y FCF
        g = info.get('earningsGrowth', 0.03)
        if g is None or g > GROWTH_CAP: g = GROWTH_CAP
            
        if wacc <= g: return None

        try:
            fcf = flujo.loc['Free Cash Flow'].iloc[0]
        except KeyError:
            op_cash = flujo.loc['Operating Cash Flow'].iloc[0]
            capex = flujo.loc['Capital Expenditure'].iloc[0]
            fcf = op_cash + capex
            
        if fcf <= 0: return None

        # 4. VALORACIÓN
        valor_empresa_total = (fcf * (1 + g)) / (wacc - g)
        valor_patrimonio = valor_empresa_total - deuda_neta
        acciones = info.get('sharesOutstanding', 1)
        valor_intrinseco = valor_patrimonio / acciones
        
        precio_compra_max = valor_intrinseco * (1 - MARGEN_SEGURIDAD)
        decision = "COMPRA FUERTE" if precio_actual < precio_compra_max else "MANTENER/VENTA"
        upside = (valor_intrinseco - precio_actual) / precio_actual

        # --- RETORNO CON DATOS DETALLADOS (NUEVO) ---
        return {
            "Ticker": ticker_symbol,
            "Empresa": nombre_oficial,  # <--- ¡AGREGAMOS ESTA LÍNEA!
            "Precio": precio_actual,
            "Valor Justo": valor_intrinseco,
            "Upside Potencial": upside,
            "Decisión": decision,
            "WACC": wacc,
            # Nuevos datos para la Caja de Cristal:
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
        return None

# --- EJECUCIÓN ---
print("Descargando lista S&P 500...")
headers = {"User-Agent": "Mozilla/5.0"}
try:
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    lista_tickers = pd.read_html(requests.get(url, headers=headers).text)[0]['Symbol'].tolist()
    lista_tickers = [item.replace('.', '-') for item in lista_tickers]
    # lista_tickers = lista_tickers[:10] # Descomenta para pruebas rápidas
except:
    lista_tickers = ['KO', 'AAPL', 'MSFT']

resultados = []
print(f"Analizando {len(lista_tickers)} empresas...")

for ticker in lista_tickers:
    print(f"Procesando: {ticker}...", end="\r")
    datos = valorar_empresa(ticker)
    if datos: resultados.append(datos)

df_final = pd.DataFrame(resultados)

# Filtros de Calidad
if not df_final.empty:
    df_final = df_final[df_final['WACC'] >= 0.05]
    df_final = df_final[df_final['Upside Potencial'] <= 2.0]
    df_final = df_final[df_final['Upside Potencial'] > 0]
    df_final.to_csv('resultados_valoracion_filtrados.csv', index=False)
    print("✅ ¡Datos actualizados exitosamente!")

