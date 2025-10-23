import streamlit as st
import pandas as pd
from io import BytesIO
import zipfile
import os
import time

# --- FUNCIONES DE PROCESAMIENTO ---

def convertir_df_a_excel(df):
    """Convierte un DataFrame a un archivo Excel en memoria (bytes)."""
    output = BytesIO()
    # Usamos xlsxwriter para crear el archivo Excel
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Plantilla Prinex')
    processed_data = output.getvalue()
    return processed_data

def procesar_zip_payhawk(zip_bytes_payhawk, df_plantilla_prinex):
    """
    Función principal que procesa el ZIP de Payhawk y rellena la plantilla de Prinex.
    
    Args:
        zip_bytes_payhawk (bytes): El contenido del archivo ZIP subido por el usuario.
        df_plantilla_prinex (pd.DataFrame): El DataFrame de la plantilla de Prinex.

    Returns:
        tuple: Una tupla conteniendo:
            - df_prinex_final (pd.DataFrame): La plantilla de Prinex rellenada.
            - archivos_pdf (dict): Un diccionario con los nombres y bytes de los PDFs.
    """
    
    # -------------------------------------------------------------------------
    # PASO 1: Descomprimir el ZIP de Payhawk en memoria
    # -------------------------------------------------------------------------
    st.write("1. Descomprimiendo archivo ZIP de Payhawk...")
    
    df_payhawk_csv = None
    archivos_pdf = {}
    
    with zipfile.ZipFile(BytesIO(zip_bytes_payhawk)) as zip_ref:
        # Buscamos el archivo CSV y los PDFs dentro del ZIP
        for nombre_archivo in zip_ref.namelist():
            # Asumimos que solo hay un CSV en el ZIP
            if nombre_archivo.lower().endswith('.csv'):
                st.write(f"   - Archivo CSV encontrado: `{nombre_archivo}`")
                with zip_ref.open(nombre_archivo) as f:
                    # Leemos el CSV. Puede que necesites ajustar el separador (sep=',')
                    df_payhawk_csv = pd.read_csv(f) 
                
            # Guardamos los PDFs
            elif nombre_archivo.lower().endswith('.pdf'):
                st.write(f"   - Archivo PDF encontrado: `{nombre_archivo}`")
                # Usamos os.path.basename para evitar problemas si vienen en carpetas
                nombre_base = os.path.basename(nombre_archivo)
                archivos_pdf[nombre_base] = zip_ref.read(nombre_archivo)

    # Validaciones
    if df_payhawk_csv is None:
        raise ValueError("No se encontró ningún archivo CSV dentro del ZIP de Payhawk.")
    if not archivos_pdf:
        st.warning("Advertencia: No se encontraron archivos PDF en el ZIP.")
    
    st.write("✅ Descompresión completada.")

    # -------------------------------------------------------------------------
    # PASO 2: Procesar y mapear los datos del CSV a la plantilla Prinex
    # -------------------------------------------------------------------------
    st.write("2. Procesando y mapeando datos...")

    # Limpiamos los nombres de las columnas por si acaso
    df_payhawk_csv.columns = df_payhawk_csv.columns.str.strip()
    df_plantilla_prinex.columns = df_plantilla_prinex.columns.str.strip()

    # Creamos el DataFrame final que tendrá la misma estructura que la plantilla
    # pero con el número de filas del CSV de Payhawk
    num_filas = len(df_payhawk_csv)
    df_prinex_final = pd.DataFrame(columns=df_plantilla_prinex.columns, index=range(num_filas))

    # --- INICIO DE LA LÓGICA DE MAPEO ---
    #
    #   ¡¡¡ IMPORTANTE !!!
    #   Aquí es donde debes definir cómo se copian los datos de una tabla a otra.
    #   Debes reemplazar 'Nombre Columna Payhawk' por el nombre real de la columna
    #   en tu archivo CSV de Payhawk.
    #
    #   Ejemplo:
    #   df_prinex_final['CODIGO SOCIEDAD'] = df_payhawk_csv['Supplier ID']
    #
    #   He puesto ejemplos basados en tu código anterior. Ajústalos a tu necesidad.
    
    # Ejemplo 1: Copia directa
    # Reemplaza 'CODIGO SOCIEDAD' si tiene otro nombre en el CSV de Payhawk
    if 'CODIGO SOCIEDAD' in df_payhawk_csv.columns:
        df_prinex_final['CODIGO SOCIEDAD'] = df_payhawk_csv['CODIGO SOCIEDAD']
    else:
        st.warning("Columna 'CODIGO SOCIEDAD' no encontrada en el CSV de Payhawk. Se dejará vacía.")

    # Ejemplo 2: Formateo de fecha
    # Reemplaza 'FECHA ASIENTO' por el nombre de la columna de fecha en tu CSV
    if 'FECHA ASIENTO' in df_payhawk_csv.columns:
        df_prinex_final['FECHA ASIENTO'] = pd.to_datetime(df_payhawk_csv['FECHA ASIENTO'], errors='coerce').dt.strftime('%d/%m/%Y')
    
    # Ejemplo 3: División de una columna en dos (CUENTA y SUBCUENTA)
    # Reemplaza 'CUENTA' por el nombre correcto en tu CSV
    if 'CUENTA' in df_payhawk_csv.columns:
        split_data = df_payhawk_csv['CUENTA'].astype(str).str.split('-', n=1, expand=True)
        df_prinex_final['CUENTA'] = split_data[0]
        df_prinex_final['SUBCUENTA'] = split_data[1].fillna('')
        
    # Ejemplo 4: Copiar otras columnas
    # Añade aquí todas las columnas que necesites mapear
    # df_prinex_final['IMPORTE'] = df_payhawk_csv['Amount']
    # df_prinex_final['CONCEPTO'] = df_payhawk_csv['Description']
    # ... etc.

    # Rellenar valores NaN con cadenas vacías para evitar problemas en la importación
    df_prinex_final = df_prinex_final.fillna('')

    st.write("✅ Mapeo de datos completado.")
    
    return df_prinex_final, archivos_pdf


# --- INTERFAZ DE USUARIO DE STREAMLIT ---

st.set_page_config(page_title="Generador de Carga Prinex", layout="wide")
st.title("🚀 Generador de Carga Masiva para Prinex desde Payhawk")
st.write("Esta herramienta automatiza la creación de la plantilla de carga para Prinex y empaqueta las facturas correspondientes.")

# Inicializar el estado de la sesión para guardar los resultados
if 'procesado' not in st.session_state:
    st.session_state.procesado = False
    st.session_state.zip_final_bytes = None
    st.session_state.df_preview = None

# Columnas para los cargadores de archivos
col1, col2 = st.columns(2)

with col1:
    st.header("1. Cargar ZIP de Payhawk")
    st.info("Sube el archivo .zip que descargas desde Payhawk. Debe contener un archivo .csv y las facturas en .pdf.")
    archivo_zip_payhawk = st.file_uploader("Selecciona el archivo ZIP", type=['zip'], key="payhawk_zip")

with col2:
    st.header("2. Cargar Plantilla Prinex")
    st.info("Sube la plantilla de Excel (.xlsx) vacía o con la estructura correcta para la importación en Prinex.")
    archivo_plantilla_prinex = st.file_uploader("Selecciona el archivo de Prinex (.xlsx)", type=['xlsx'], key="prinex_template")

st.divider()

# Botón para iniciar el procesamiento
st.header("3. Generar Archivo de Carga")
if st.button("✨ Generar Archivo ZIP para Prinex", type="primary"):
    if archivo_zip_payhawk is not None and archivo_plantilla_prinex is not None:
        try:
            tiempo_inicio = time.time()
            
            # Leer los archivos subidos en memoria
            zip_bytes = archivo_zip_payhawk.getvalue()
            df_plantilla = pd.read_excel(archivo_plantilla_prinex)
            
            with st.spinner('Procesando archivos... por favor, espera.'):
                # Llamar a la función principal de procesamiento
                df_prinex_final, archivos_pdf = procesar_zip_payhawk(zip_bytes, df_plantilla)
                
                st.write("3. Creando el archivo Excel final...")
                excel_final_bytes = convertir_df_a_excel(df_prinex_final)
                st.write("✅ Archivo Excel generado.")
                
                st.write("4. Creando el archivo ZIP de salida...")
                zip_buffer_salida = BytesIO()
                with zipfile.ZipFile(zip_buffer_salida, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                    # Añadir la plantilla de Excel al ZIP
                    zip_file.writestr("plantilla_prinex_cargada.xlsx", excel_final_bytes)
                    
                    # Añadir todas las facturas PDF al ZIP
                    for nombre_pdf, bytes_pdf in archivos_pdf.items():
                        zip_file.writestr(f"facturas/{nombre_pdf}", bytes_pdf)
                
                st.write("✅ Archivo ZIP de salida creado.")

            tiempo_fin = time.time()
            st.success(f"¡Proceso completado con éxito en {tiempo_fin - tiempo_inicio:.2f} segundos!")
            
            # Guardar los resultados en el estado de la sesión para mostrarlos
            st.session_state.procesado = True
            st.session_state.zip_final_bytes = zip_buffer_salida.getvalue()
            st.session_state.df_preview = df_prinex_final.head()

        except Exception as e:
            st.error(f"Ha ocurrido un error durante el procesamiento: {e}")
            st.session_state.procesado = False
    else:
        st.warning("⚠️ Debes cargar ambos archivos para poder generar el archivo de carga.")

# Mostrar los resultados si el proceso fue exitoso
if st.session_state.procesado:
    st.divider()
    st.header("4. Descargar Resultados")
    
    st.subheader("Previsualización de la Plantilla Generada")
    st.dataframe(st.session_state.df_preview)
    
    st.download_button(
        label="📥 Descargar TODO (.zip)",
        data=st.session_state.zip_final_bytes,
        file_name="carga_prinex_con_facturas.zip",
        mime="application/zip",
        type="primary"
    )
    st.info("El archivo ZIP descargado contiene la plantilla de Excel rellenada y una carpeta con todas las facturas en PDF.")