import yfinance as yf
import pandas as pd
#import pandas_datareader.data as web # Necesario para bajar la lista del S&P 500
import numpy as np
import requests

# --- 1. CONFIGURACIÓN GLOBAL ---
MARKET_RETURN = 0.08      # 8% Esperado
GROWTH_CAP = 0.03         # Tope de crecimiento (3%)
MARGEN_SEGURIDAD = 0.20   # 20% de descuento requerido

# Obtenemos la Tasa Libre de Riesgo UNA sola vez para no llamar a la API 500 veces
tnx = yf.Ticker("^TNX")
# A veces falla si el mercado está cerrado justo en ese seg, ponemos un valor por defecto seguro
try:
    RISK_FREE_RATE = tnx.history(period="1d")['Close'].iloc[-1] / 100
except:
    RISK_FREE_RATE = 0.042 # 4.2% backup
    print("Usando tasa libre de riesgo por defecto (4.2%)")

print(f"Tasa Libre de Riesgo actual: {RISK_FREE_RATE:.2%}")

# --- 2. LA FUNCIÓN DE VALORACIÓN (TU LÓGICA ENCAPSULADA) ---
def valorar_empresa(ticker_symbol):
    try:
        empresa = yf.Ticker(ticker_symbol)
        info = empresa.info
        
        # Filtro rápido: Si no tiene precio o market cap, saltamos
        if 'currentPrice' not in info or 'marketCap' not in info:
            return None

        precio_actual = info['currentPrice']
        market_cap = info['marketCap']
        beta = info.get('beta', 1.0) # Si no hay beta, asumimos 1 (riesgo mercado)

        # --- EXTRACCIÓN DE DATOS FINANCIEROS ---
        # Usamos fast_info o info para velocidad, pero financials para precisión
        balance = empresa.balance_sheet
        resultados = empresa.financials
        flujo = empresa.cashflow
        
        # Si las tablas están vacías, saltamos
        if balance.empty or resultados.empty or flujo.empty:
            return None

        # 1. DEUDA
        try:
            deuda_total = balance.loc['Total Debt'].iloc[0]
        except KeyError:
            try:
                deuda_total = balance.loc['Total Debt And Capital Lease Obligation'].iloc[0]
            except KeyError:
                deuda_total = 0 # Asumimos 0 si no reporta deuda explícita (riesgoso pero necesario para automatizar)

        total_cash = info.get("totalCash", 0)
        deuda_neta = deuda_total - total_cash
        enterprise_value = market_cap + deuda_neta
        
        # Evitar errores de división por cero
        if enterprise_value <= 0: return None

        # 2. COSTO DEL CAPITAL (WACC)
        # Costo del Patrimonio (Ke)
        ke = RISK_FREE_RATE + beta * (MARKET_RETURN - RISK_FREE_RATE)
        
        # Costo de la Deuda (Kd)
        try:
            interest_expense = abs(resultados.loc['Interest Expense'].iloc[0])
            tax_provision = resultados.loc['Tax Provision'].iloc[0]
            pretax_income = resultados.loc['Pretax Income'].iloc[0]
            
            tax_rate = tax_provision / pretax_income if pretax_income != 0 else 0.21
            if tax_rate < 0 or tax_rate > 0.5: tax_rate = 0.21 # Normalizar casos raros
            
            costo_deuda_bruto = interest_expense / deuda_total if deuda_total > 0 else 0
            kd = costo_deuda_bruto * (1 - tax_rate)
        except:
            kd = 0.04 # Un Kd genérico si fallan los datos contables

        # WACC
        w_e = market_cap / enterprise_value
        w_d = deuda_neta / enterprise_value
        wacc = (w_e * ke) + (w_d * kd)
        
        # 3. CRECIMIENTO (g)
        g = info.get('earningsGrowth', 0.03)
        if g is None or g > GROWTH_CAP: # Tu lógica conservadora
            g = GROWTH_CAP
            
        # Fórmula de Gordon requiere que WACC > g
        if wacc <= g:
            return None # Matemáticamente imposible valorar con Gordon si g > WACC

        # 4. FLUJO DE CAJA LIBRE (FCF)
        try:
            fcf = flujo.loc['Free Cash Flow'].iloc[0]
        except KeyError:
            op_cash = flujo.loc['Operating Cash Flow'].iloc[0]
            capex = flujo.loc['Capital Expenditure'].iloc[0]
            fcf = op_cash + capex
            
        if fcf <= 0:
            return None # Gordon Growth no sirve para empresas que pierden dinero hoy

        # 5. VALORACIÓN FINAL
        valor_empresa_total = (fcf * (1 + g)) / (wacc - g)
        valor_patrimonio = valor_empresa_total - deuda_neta
        acciones = info.get('sharesOutstanding', 1)
        
        valor_intrinseco = valor_patrimonio / acciones
        
        # Margen de seguridad
        precio_compra_max = valor_intrinseco * (1 - MARGEN_SEGURIDAD)
        
        decision = "COMPRA FUERTE" if precio_actual < precio_compra_max else "MANTENER/VENTA"
        upside = (valor_intrinseco - precio_actual) / precio_actual

        return {
            "Ticker": ticker_symbol,
            "Precio": precio_actual,
            "Valor Justo": valor_intrinseco,
            "Precio Max Compra": precio_compra_max,
            "Upside Potencial": upside,
            "WACC": wacc,
            "Decisión": decision
        }

    except Exception as e:
        # Si algo falla en una empresa, no detenemos el código, solo la ignoramos
        return None

# --- 3. OBTENCIÓN DE TICKERS (S&P 500 COMO EJEMPLO) ---
# --- 3. OBTENCIÓN DE TICKERS (S&P 500) CON DISFRAZ ---
print("Descargando lista de S&P 500 desde Wikipedia...")

url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'

# Este es el "disfraz": Le decimos que somos un navegador Chrome normal
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

try:
    # 1. Hacemos la petición con los headers (el disfraz)
    response = requests.get(url, headers=headers)
    
    # 2. Le damos el texto HTML ya descargado a Pandas
    # Pandas buscará tablas dentro de ese texto
    tablas = pd.read_html(response.text)
    
    # La tabla de tickers suele ser la primera [0]
    df_sp500 = tablas[0]
    lista_tickers = df_sp500['Symbol'].tolist()
    
    # Limpieza: Wikipedia usa puntos (BRK.B) pero Yahoo usa guiones (BRK-B)
    lista_tickers = [item.replace('.', '-') for item in lista_tickers]
    
    # --- ¡IMPORTANTE! ---
    # Para probar rápido, limitamos a los primeros 10.
    # Si quieres correr los 500, comenta la siguiente línea con un #
    #lista_tickers = lista_tickers[:10] 
    
    print(f"✅ Éxito. Analizando {len(lista_tickers)} empresas...")

except Exception as e:
    print(f"❌ Error descargando lista: {e}")
    print("Usando lista de emergencia manual.")
    lista_tickers = ['KO', 'AAPL', 'MSFT', 'GOOGL', 'TSLA', 'JPM', 'XOM']

# --- 4. EJECUCIÓN MASIVA ---
resultados = []

for ticker in lista_tickers:
    print(f"Procesando: {ticker}...", end="\r") # end="\r" sobreescribe la línea
    datos = valorar_empresa(ticker)
    if datos:
        resultados.append(datos)

# --- 5. RESULTADOS, FILTRADO Y EXPORTACIÓN ---
df_resultados = pd.DataFrame(resultados)

if not df_resultados.empty:
    print(f"\nTotal empresas analizadas inicialmente: {len(df_resultados)}")
    
    # --- APLICACIÓN DE FILTROS DE CALIDAD ---
    
    # 1. Filtro de WACC Realista (Mínimo 5%)
    # Explicación: Un WACC < 5% es sospechoso cuando la tasa libre de riesgo es 4.2%.
    df_final = df_resultados[df_resultados['WACC'] >= 0.05].copy()
    
    # 2. Filtro de Upside Creíble (Máximo 200%)
    # Explicación: Si promete triplicar tu dinero (+200%), suele ser un error de datos o quiebra.
    df_final = df_final[df_final['Upside Potencial'] <= 2.0]
    
    # 3. Solo mostramos lo que sea "Compra" (Upside positivo)
    df_final = df_final[df_final['Upside Potencial'] > 0]
    
    # Ordenar por las mejores oportunidades
    df_final = df_final.sort_values(by="Upside Potencial", ascending=False)
    
    print(f"Empresas tras filtrar WACC<5% y Upside>200%: {len(df_final)}")

    # --- MOSTRAR Y GUARDAR ---
    pd.options.display.float_format = '{:.2f}'.format
    print("\n--- TOP OPORTUNIDADES FILTRADAS ---")
    print(df_final[['Ticker', 'Precio', 'Valor Justo', 'Upside Potencial', 'WACC']].head(20))
    
    # Exportar a CSV limpio
    nombre_archivo = 'resultados_valoracion_filtrados.csv'
    df_final.to_csv(nombre_archivo, index=False)
    print(f"\n✅ ¡Listo! Resultados guardados en '{nombre_archivo}'")
    
else:
    print("No se encontraron resultados válidos.")