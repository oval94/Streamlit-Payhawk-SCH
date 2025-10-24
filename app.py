import streamlit as st
import pandas as pd
from io import BytesIO
import zipfile
import os
import time

# --- FUNCIONES AUXILIARES ---

def convertir_df_a_excel(df):
    """Convierte un DataFrame a un archivo Excel en memoria (bytes)."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Plantilla Prinex')
    return output.getvalue()

def validar_archivos_cargados(zip_bytes, df_plantilla):
    """
    Realiza una validación completa de ambos archivos y devuelve una lista de todos los errores encontrados.
    """
    lista_errores = []

    # 1. Validación del contenido del ZIP
    csv_encontrado = False
    pdf_encontrado = False
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zip_ref:
        for nombre_archivo in zip_ref.namelist():
            if nombre_archivo.lower().endswith('.csv'):
                csv_encontrado = True
            elif nombre_archivo.lower().endswith('.pdf'):
                pdf_encontrado = True
    
    if not csv_encontrado:
        lista_errores.append("El archivo ZIP no contiene el archivo CSV de Payhawk requerido.")
    
    if not pdf_encontrado:
        lista_errores.append("El archivo ZIP no contiene ninguna factura en formato PDF.")

    # 2. Validación de la estructura de la plantilla Prinex
    columnas_requeridas_prinex = [
        'SOCIEDAD', 'ORDEN', 'CODIGO', 'TOTAL', 'OP.ALQ', 'D347', 
        'TIPO.FRA', 'DIARIO1', 'BASE1', 'IVA1', 'CUOTA1', 'PROYECTO', 
        'IMPORTE_GASTO', 'CTA_GASTO', 'SCTA_GASTO', 'NOMBRE', 
        'CARACTERISTICA', 'RUTA', 'ETAPA'
    ]
    columnas_actuales = df_plantilla.columns.str.strip().tolist()
    columnas_faltantes = [col for col in columnas_requeridas_prinex if col not in columnas_actuales]

    if columnas_faltantes:
        error_cols = f"La plantilla de Prinex no es correcta. Faltan o están mal escritas las siguientes columnas: **{', '.join(columnas_faltantes)}**"
        lista_errores.append(error_cols)
        
    return lista_errores

# --- FUNCIÓN DE PROCESAMIENTO PRINCIPAL ---

def procesar_zip_payhawk(zip_bytes_payhawk, df_plantilla_prinex):
    """
    Función que procesa el ZIP de Payhawk y rellena la plantilla de Prinex.
    ASUME que las validaciones de archivos ya se han realizado.
    """
    st.write("1. Descomprimiendo archivo ZIP de Payhawk...")
    df_payhawk = None
    archivos_pdf = {}
    with zipfile.ZipFile(BytesIO(zip_bytes_payhawk)) as zip_ref:
        for nombre_archivo in zip_ref.namelist():
            if nombre_archivo.lower().endswith('.csv'):
                st.write(f"   - Archivo CSV (PAYHAWK) encontrado: `{nombre_archivo}`")
                with zip_ref.open(nombre_archivo) as f:
                    df_payhawk = pd.read_csv(f)
            elif nombre_archivo.lower().endswith('.pdf'):
                nombre_base = os.path.basename(nombre_archivo)
                archivos_pdf[nombre_base] = zip_ref.read(nombre_archivo)
    st.write("✅ Descompresión completada.")

    st.write("2. Mapeando datos...")
    df_payhawk.columns = df_payhawk.columns.str.strip()
    df_plantilla_prinex.columns = df_plantilla_prinex.columns.str.strip()
    num_filas = len(df_payhawk)
    df_prinex_final = pd.DataFrame(columns=df_plantilla_prinex.columns, index=range(num_filas))

    df_prinex_final['SOCIEDAD'] = 666
    df_prinex_final['CODIGO'] = 4444
    df_prinex_final['DIARIO_CONTB'] = 1
    df_prinex_final['OP.ALQ'] = 'N'
    df_prinex_final['D347'] = 'S'
    df_prinex_final['TIPO.FRA'] = 'F'
    df_prinex_final['DIARIO1'] = 1
    df_prinex_final['CARACTERISTICA'] = 'Facturas payhawk'
    df_prinex_final['RUTA'] = 1
    df_prinex_final['ETAPA'] = 'PRODUCCIÓN'

    column_map = {
        'ORDEN': 'Expense ID', 'NUM.FRA': 'Document Number', 'IMP.BRUTO': 'Net Amount (EUR)',
        'TOTAL': 'Total Amount (EUR)', 'BASE1': 'Net Amount (EUR)', 'IVA1': 'Tax Rate %',
        'CUOTA1': 'Tax Amount (EUR)', 'PROYECTO': 'Promoción External ID',
        'IMPORTE_GASTO': 'Net Amount (EUR)', 'NOMBRE': 'File Name 1'
    }
    for prinex_col, payhawk_col in column_map.items():
        if payhawk_col in df_payhawk.columns:
            df_prinex_final[prinex_col] = df_payhawk[payhawk_col]
        else:
            st.warning(f"Advertencia: La columna '{payhawk_col}' no se encontró en PAYHAWK. La columna '{prinex_col}' quedará vacía.")

    if 'Document Date' in df_payhawk.columns:
        df_prinex_final['FECHA.FRA'] = pd.to_datetime(df_payhawk['Document Date'], errors='coerce').dt.strftime('%d/%m/%Y')
    else:
        st.warning("Advertencia: La columna 'Document Date' no se encontró en PAYHAWK. 'FECHA.FRA' quedará vacía.")

    if 'Account Code' in df_payhawk.columns:
        split_data = df_payhawk['Account Code'].astype(str).str.split('-', n=1, expand=True)
        df_prinex_final['CTA_GASTO'] = split_data[0]
        df_prinex_final['SCTA_GASTO'] = split_data[1].fillna('') if 1 in split_data.columns else ''
    else:
        st.warning("Advertencia: 'Account Code' no encontrada en PAYHAWK. 'CTA_GASTO' y 'SCTA_GASTO' quedarán vacías.")
    
    df_prinex_final = df_prinex_final.fillna('')
    st.write("✅ Mapeo de datos completado.")
    return df_prinex_final, archivos_pdf

# --- INTERFAZ DE USUARIO DE STREAMLIT ---

st.set_page_config(page_title="Generador de Carga Prinex", layout="wide")
st.title("🚀 Generador de Carga Masiva para Prinex desde Payhawk")
st.write("Esta herramienta automatiza la creación de la plantilla de carga para Prinex y empaqueta las facturas correspondientes.")

if 'procesado' not in st.session_state:
    st.session_state.procesado = False
    st.session_state.zip_final_bytes = None
    st.session_state.df_preview = None

col1, col2 = st.columns(2)
with col1:
    st.header("1. Cargar ZIP de Payhawk")
    st.info("Sube el archivo .zip que descargas desde Payhawk. Debe contener un archivo .csv y las facturas en .pdf.")
    archivo_zip_payhawk = st.file_uploader("Selecciona el archivo ZIP", type=['zip'], key="payhawk_zip")
with col2:
    st.header("2. Cargar Plantilla Prinex")
    st.info("Sube la plantilla de Excel (.xlsx) vacía con la estructura correcta para la importación en Prinex.")
    archivo_plantilla_prinex = st.file_uploader("Selecciona el archivo de Prinex (.xlsx)", type=['xlsx'], key="prinex_template")

st.divider()
st.header("3. Generar Archivo de Carga")

if st.button("✨ Generar Archivo ZIP para subir datos a Prinex", type="primary"):
    if archivo_zip_payhawk is not None and archivo_plantilla_prinex is not None:
        try:
            # --- FASE DE VALIDACIÓN CONSOLIDADA ---
            st.write("Iniciando validaciones previas...")
            zip_bytes = archivo_zip_payhawk.getvalue()
            df_plantilla = pd.read_excel(archivo_plantilla_prinex)
            
            # Llamamos a la función que revisa todo y devuelve una lista de errores
            errores_encontrados = validar_archivos_cargados(zip_bytes, df_plantilla)

            # Si la lista de errores NO está vacía, los mostramos todos y detenemos
            if errores_encontrados:
                mensaje_error_final = "**Se encontraron los siguientes problemas en los archivos cargados:**\n"
                for error in errores_encontrados:
                    mensaje_error_final += f"\n- {error}"
                st.error(mensaje_error_final)
                st.session_state.procesado = False
            else:
                # Si no hay errores, procedemos con el procesamiento
                st.write("✅ Todas las validaciones son correctas. Iniciando procesamiento...")
                tiempo_inicio = time.time()
                with st.spinner('Procesando archivos...'):
                    df_prinex_final, archivos_pdf = procesar_zip_payhawk(zip_bytes, df_plantilla)
                    
                    st.write("3. Creando el archivo Excel final...")
                    excel_final_bytes = convertir_df_a_excel(df_prinex_final)
                    st.write("✅ Archivo Excel generado.")
                    
                    st.write("4. Creando el archivo ZIP de salida...")
                    zip_buffer_salida = BytesIO()
                    with zipfile.ZipFile(zip_buffer_salida, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                        zip_file.writestr("plantilla_prinex_cargada.xlsx", excel_final_bytes)
                        for nombre_pdf, bytes_pdf in archivos_pdf.items():
                            zip_file.writestr(f"facturas/{nombre_pdf}", bytes_pdf)
                    st.write("✅ Archivo ZIP de salida creado.")

                tiempo_fin = time.time()
                st.success(f"¡Proceso completado con éxito en {tiempo_fin - tiempo_inicio:.2f} segundos!")
                
                st.session_state.procesado = True
                st.session_state.zip_final_bytes = zip_buffer_salida.getvalue()
                st.session_state.df_preview = df_prinex_final.head()

        except Exception as e:
            st.error(f"Ha ocurrido un error inesperado durante la ejecución: {e}")
            st.session_state.procesado = False
    else:
        st.warning("⚠️ Debes cargar ambos archivos para poder generar el archivo de carga.")

if st.session_state.procesado:
    st.divider()
    st.header("4. Descargar Resultados")
    st.subheader("Previsualización de la Plantilla Generada (5 primeras filas)")
    st.dataframe(st.session_state.df_preview)
    st.download_button(
        label="📥 Descargar TODO (.zip)",
        data=st.session_state.zip_final_bytes,
        file_name="carga_prinex_con_facturas.zip",
        mime="application/zip",
        type="primary"
    )
    st.info("El archivo ZIP descargado contiene la plantilla de Excel rellenada y una carpeta con todas las facturas en PDF.")