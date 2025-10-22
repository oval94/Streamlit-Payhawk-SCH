import streamlit as st
import pandas as pd
from io import BytesIO
import numpy as np
import time
import zipfile 

def procesar_datos(df_payhawk, df_prinex):
    df_payhawk.columns = df_payhawk.columns.str.strip()
    df_prinex.columns = df_prinex.columns.str.strip()
    st.write("1. Validando archivos...")
    if 'CODIGO SOCIEDAD' not in df_payhawk.columns:
        raise ValueError("El archivo PAYHAWK no es correcto. No se encontró la columna 'CODIGO SOCIEDAD'.")
    if 'CÓDIGO REPARTO' not in df_prinex.columns:
        raise ValueError("El archivo PRINEX no es correcto. No se encontró la columna 'CÓDIGO REPARTO'.")
    st.write("✅ Archivos validados correctamente.")
    st.write("2. Procesando y enriqueciendo datos de PAYHAWK...")
    if 'FECHA ASIENTO' in df_payhawk.columns:
        df_payhawk['FECHA ASIENTO'] = pd.to_datetime(df_payhawk['FECHA ASIENTO'], errors='coerce').dt.strftime('%d/%m/%Y')
    if 'CUENTA' in df_payhawk.columns:
        split_data = df_payhawk['CUENTA'].astype(str).str.split('-', n=1, expand=True)
        df_payhawk['CUENTA'] = split_data[0]
        subcuenta_data = split_data[1].fillna('')
        if 'SUBCUENTA' in df_payhawk.columns:
            df_payhawk['SUBCUENTA'] = subcuenta_data
        else:
            pos_cuenta = df_payhawk.columns.get_loc('CUENTA')
            df_payhawk.insert(pos_cuenta + 1, 'SUBCUENTA', subcuenta_data)
    num_filas = len(df_payhawk)
    if num_filas > 0:
        contador = np.repeat(np.arange(1, (num_filas // 2) + 2), 2)[:num_filas]
        df_payhawk['NUM DOCUMENTO'] = contador
    columna_g_nombre = df_payhawk.columns[6]
    df_payhawk[columna_g_nombre] = df_payhawk[columna_g_nombre].astype(str).str.split('-', n=1, expand=True)[0]
    st.write("✅ Procesamiento de PAYHAWK completado.")
    st.write("3. Generando plantilla PRINEX principal...")
    df_prinex_final = pd.DataFrame(columns=df_prinex.columns, index=range(len(df_payhawk)))
    columnas_fuente = df_payhawk.columns[:13]
    columnas_destino = df_prinex_final.columns[:13]
    df_prinex_final[columnas_destino] = df_payhawk[columnas_fuente].values
    columna_m_nombre = df_prinex_final.columns[12]
    df_prinex_final[columna_m_nombre] = ""
    st.write("✅ Plantilla PRINEX principal generada.")
    st.write("4. Generando plantilla de Centro de Coste...")
    df_centro_coste_temp = df_prinex_final.copy()
    if 'CENTRO DE COSTE' in df_payhawk.columns:
        df_centro_coste_temp['CENTRO DE COSTE'] = df_payhawk['CENTRO DE COSTE'].values
    else:
        df_centro_coste_temp['CENTRO DE COSTE'] = ""
        st.warning("Advertencia: No se encontró la columna 'CENTRO DE COSTE' en el archivo Payhawk. Se ha dejado vacía.")
    mapa_renombre = {
        'DIARIO': 'CODIGO DIARIO',
        'NUM DOCUMENTO': 'NUMERO DOCUMENTO',
        'NUM LINEA': 'NÚMERO LINEA'
    }
    df_centro_coste_temp = df_centro_coste_temp.rename(columns=mapa_renombre)
    columnas_requeridas_cc = [
        'CODIGO SOCIEDAD', 'EJERCICIO', 'CODIGO DIARIO', 
        'NUMERO DOCUMENTO', 'NÚMERO LINEA', 'CENTRO DE COSTE', 
        'IMPORTE', 'MONEDA'
    ]
    columnas_faltantes = [col for col in columnas_requeridas_cc if col not in df_centro_coste_temp.columns]
    if columnas_faltantes:
        raise ValueError(f"No se pudieron encontrar las siguientes columnas para crear el Centro de Coste: {', '.join(columnas_faltantes)}")
    df_final_cc = df_centro_coste_temp[columnas_requeridas_cc]
    st.write("✅ Plantilla de Centro de Coste generada.")
    return df_prinex_final, df_final_cc

def convertir_df_a_csv(df):
    return df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')


# INTERFAZ DE USUARIO DE STREAMLIT
st.set_page_config(page_title="Generador de Plantillas", layout="wide")

# Limpiar nombre de las columnas al cargar
st.title("📄 Generador de plantillas PayHawk - Prinex")
st.write("Carga los archivos de Payhawk y Prinex para generar las plantillas de importación.")

# Esto asegura que las variables existan desde el principio.
if 'procesado' not in st.session_state:
    st.session_state.procesado = False
    st.session_state.csv_prinex = None
    st.session_state.csv_cc = None
    st.session_state.df_prinex_head = None
    st.session_state.df_cc_head = None

# Crear los dos cargadores de archivos en columnas
col1, col2 = st.columns(2)
with col1:
    st.header("1. Cargar Archivo Payhawk")
    archivo_payhawk = st.file_uploader("Selecciona el archivo de Payhawk (.xlsx)", type=['xlsx'], key="payhawk")
with col2:
    st.header("2. Cargar Archivo Prinex")
    archivo_prinex = st.file_uploader("Selecciona el archivo de Prinex (.xlsx)", type=['xlsx'], key="prinex")

st.divider()

# Crear el botón para procesar los archivos
st.header("3. Generar las Plantillas")
if st.button("✨ Generar Plantillas", type="primary"):
    if archivo_payhawk is not None and archivo_prinex is not None:
        if archivo_payhawk.name == archivo_prinex.name:
            st.error("Error: Has seleccionado el mismo archivo para Payhawk y Prinex.")
        else:
            try:
                tiempo_inicio = time.time()
                df_payhawk = pd.read_excel(archivo_payhawk, engine='openpyxl')
                df_prinex = pd.read_excel(archivo_prinex, engine='openpyxl')
                
                with st.spinner('Procesando datos... por favor, espera.'):
                    df_final_prinex, df_final_cc = procesar_datos(df_payhawk, df_prinex)
                
                tiempo_fin = time.time()
                tiempo_total = tiempo_fin - tiempo_inicio
                st.success(f"¡Proceso completado con éxito en {tiempo_total:.2f} segundos!")
                
                # Guardar los resultados en el estado de la sesión
                st.session_state.csv_prinex = convertir_df_a_csv(df_final_prinex)
                st.session_state.csv_cc = convertir_df_a_csv(df_final_cc)
                st.session_state.df_prinex_head = df_final_prinex.head()
                st.session_state.df_cc_head = df_final_cc.head()
                st.session_state.procesado = True # Activamos la bandera para mostrar los resultados

            except Exception as e:
                st.error(f"Ha ocurrido un error durante la ejecución: {e}")
                st.session_state.procesado = False # Si hay error, no mostramos nada
    else:
        st.warning("⚠️ Debes cargar ambos archivos antes de poder generar las plantillas.")

# Mostrar resultados si la bandera 'procesado' está activa
# Este bloque de código está FUERA del `if st.button(...)`
# Se ejecutará en cada refresco, y mostrará los resultados si existen en el estado de sesión
if st.session_state.procesado:
    st.subheader("Resultados Generados")
    
    # Crear un archivo ZIP en memoria
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        zip_file.writestr("plantilla_prinex.csv", st.session_state.csv_prinex)
        zip_file.writestr("plantilla_centro_coste.csv", st.session_state.csv_cc)
    
    # Botón para descargar todo en un ZIP
    st.download_button(
        label="📥 Descargar TODO (.zip)",
        data=zip_buffer.getvalue(),
        file_name="plantillas_generadas.zip",
        mime="application/zip",
        type="primary"
    )
    
    st.divider()

    #Botones para descargar por separado
    res_col1, res_col2 = st.columns(2)
    with res_col1:
        st.markdown("#### Plantilla Principal")
        st.dataframe(st.session_state.df_prinex_head)
        st.download_button(
            label="Descargar Plantilla Principal (.csv)",
            data=st.session_state.csv_prinex, # Leer datos desde el estado de sesión
            file_name="plantilla_prinex.csv",
            mime="text/csv"
        )
    with res_col2:
        st.markdown("#### Plantilla Centro de Coste")
        st.dataframe(st.session_state.df_cc_head)
        st.download_button(
            label="Descargar Centro de Coste (.csv)",
            data=st.session_state.csv_cc, # Leer datos desde el estado de sesión
            file_name="plantilla_centro_coste.csv",
            mime="text/csv"
        )