import streamlit as st
import pandas as pd
import joblib

# Configuración de la página
st.set_page_config(page_title="Recomendador Comercial - Cruzimex", layout="wide")

st.title("🎯 Sistema de Recomendación Comercial - Cruzimex")
st.markdown("Herramienta interactiva para preventivos y supervisores en campo.")

# Cargar datos desde los archivos .joblib (con caché para que sea ultra rápido)
@st.cache_resource
def cargar_datos():
    df_cli = joblib.load('df_clientes.joblib')
    df_ven = joblib.load('df_ventas.joblib')
    df_cos = joblib.load('df_coseno.joblib')
    stock = joblib.load('stock_disponible.joblib')
    return df_cli, df_ven, df_cos, stock

try:
    df_clientes, df_ventas, df_coseno, stock_disponible = cargar_datos()
    st.sidebar.success("✅ Datos y modelos cargados correctamente")
except Exception as e:
    st.sidebar.error(f"❌ Error al cargar archivos .joblib: {e}")
    st.stop()

# --- PANEL LATERAL: FILTROS DESPLEGABLES ---
st.sidebar.header("🔍 Filtros de Búsqueda")

# 1. Filtro de Vendedor
vendedores_disponibles = ["TODOS"] + sorted(df_clientes['VENDEDOR'].dropna().unique().tolist())
vendedor_sel = st.sidebar.selectbox("Seleccionar Vendedor:", vendedores_disponibles)

# Filtrar DataFrame según Vendedor
df_filtrado = df_clientes.copy()
if vendedor_sel != "TODOS":
    df_filtrado = df_filtrado[df_filtrado['VENDEDOR'] == vendedor_sel]

# 2. Filtro de Zona
zonas_disponibles = ["TODAS"] + sorted(df_filtrado['ZONA'].dropna().unique().tolist())
zona_sel = st.sidebar.selectbox("Seleccionar Zona:", zonas_disponibles)

if zona_sel != "TODAS":
    df_filtrado = df_filtrado[df_filtrado['ZONA'] == zona_sel]

# 3. Filtro de Clasificación / Canal
clasificaciones_disponibles = ["TODAS"] + sorted(df_filtrado['CLASIFICACION'].dropna().unique().tolist())
clasificacion_sel = st.sidebar.selectbox("Seleccionar Clasificación:", clasificaciones_disponibles)

if clasificacion_sel != "TODAS":
    df_filtrado = df_filtrado[df_filtrado['CLASIFICACION'] == clasificacion_sel]

# 4. Selector de Cliente (Muestra Código + Nombre de Compañía de forma segura)
if df_filtrado.empty:
    st.sidebar.warning("⚠️ No hay clientes con esta combinación de filtros.")
    st.stop()

df_filtrado['ETIQUETA_CLIENTE'] = df_filtrado['CODIGO'].astype(str) + " - " + df_filtrado['NOMBRE COMPANIA'].astype(str)
clientes_opciones = sorted(df_filtrado['ETIQUETA_CLIENTE'].unique().tolist())

cliente_elegido = st.sidebar.selectbox("Seleccionar Cliente:", clientes_opciones)

# Extraer el código numérico del cliente seleccionado
codigo_cliente = int(cliente_elegido.split(" - ")[0])

top_n = st.sidebar.slider("Cantidad de recomendaciones:", min_value=1, max_value=15, value=5)

# --- LÓGICA PRINCIPAL DE RECOMENDACIÓN ---
cli_info = df_clientes[df_clientes['CODIGO'] == codigo_cliente].iloc[0]
canal_cli = cli_info['CLASIFICACION']
clase_pareto_cli = cli_info.get('CLASE_PARETO', 'C')

st.subheader("📋 Información del Cliente Seleccionado")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Código", cli_info['CODIGO'])
col2.metric("Compañía", cli_info['NOMBRE COMPANIA'])
col3.metric("Clasificación / Canal", canal_cli)
col4.metric("Clase Pareto", clase_pareto_cli)

st.divider()

# Obtener historial del cliente
historial = df_ventas[df_ventas['Cliente'] == codigo_cliente]
subclases_compradas_raw = historial['Descripcion SubClase'].unique() if not historial.empty else []
subclases_compradas = [s for s in subclases_compradas_raw if pd.notna(s) and s in df_coseno.columns]

articulos_con_stock = set(stock_disponible['COD'])
recomendaciones = []

if len(subclases_compradas) > 0:
    similares = df_coseno[subclases_compradas].mean(axis=1).sort_values(ascending=False)
    similares = similares.drop(labels=subclases_compradas, errors='ignore')

    for subclase_sugerida, score in similares.items():
        if score <= 0: continue
        articulos_subclase = df_ventas[df_ventas['Descripcion SubClase'] == subclase_sugerida][['Articulo', 'Descripcion Articulo']].drop_duplicates()

        for _, row in articulos_subclase.iterrows():
            cod_art = str(row['Articulo']).strip()
            if cod_art in articulos_con_stock:
                match_stock = stock_disponible[stock_disponible['COD'] == cod_art]
                cant_stock = float(match_stock['CANT'].values[0]) if not match_stock.empty else 0.0

                recomendaciones.append({
                    'Código Producto': cod_art,
                    'Producto': row['Descripcion Articulo'],
                    'Subclase': subclase_sugerida,
                    'Stock en Piso': cant_stock,
                    'Afinidad': f"{round(score * 100, 1)}%",
                    'Motivo': "Basado en similitud de consumo con su historial"
                })
            if len(recomendaciones) >= top_n: break
        if len(recomendaciones) >= top_n: break
else:
    clientes_canal = df_clientes[df_clientes['CLASIFICACION'] == canal_cli]['CODIGO']
    top_canal = df_ventas[df_ventas['Cliente'].isin(clientes_canal)]
    top_subclases = top_canal['Descripcion SubClase'].value_counts().index.tolist()
    
    for subclase_sugerida in top_subclases:
        articulos_subclase = df_ventas[df_ventas['Descripcion SubClase'] == subclase_sugerida][['Articulo', 'Descripcion Articulo']].drop_duplicates()
        for _, row in articulos_subclase.iterrows():
            cod_art = str(row['Articulo']).strip()
            if cod_art in articulos_con_stock:
                match_stock = stock_disponible[stock_disponible['COD'] == cod_art]
                cant_stock = float(match_stock['CANT'].values[0]) if not match_stock.empty else 0.0

                recomendaciones.append({
                    'Código Producto': cod_art,
                    'Producto': row['Descripcion Articulo'],
                    'Subclase': subclase_sugerida,
                    'Stock en Piso': cant_stock,
                    'Afinidad': "Top Canal",
                    'Motivo': "Producto estrella del canal (Cliente nuevo)"
                })
            if len(recomendaciones) >= top_n: break
        if len(recomendaciones) >= top_n: break

st.subheader("💡 Productos Recomendados")
if recomendaciones:
    df_rec = pd.DataFrame(recomendaciones)
    st.dataframe(df_rec, use_container_width=True)
else:
    st.info("No hay recomendaciones disponibles con stock actual para este cliente.")
