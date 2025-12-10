import streamlit as st
import os
import json
import tempfile
import base64
import atexit
import glob
import shutil
import pandas as pd
from dotenv import load_dotenv

# Try to load from .env
load_dotenv()

# Add parent directory to path to ensure imports work
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.backend import extract_catalytic_data, configure_genai, flatten_data_to_csv
    from src.models import ExtractionResult
except ImportError as e:
    st.error(f"Error importando módulos backend: {e}")

# --- Temp File Cleanup ---
if 'temp_files' not in st.session_state:
    st.session_state['temp_files'] = []

def cleanup_temp_files():
    for path in st.session_state.get('temp_files', []):
        try:
            if os.path.exists(path):
                os.remove(path)
        except:
            pass
    st.session_state['temp_files'] = []

atexit.register(cleanup_temp_files)

# --- UTILITY: FIND ALL EVIDENCE FILES IN DIRECTORY ---
def find_article_bundles(root_dir: str):
    """
    Escanea carpetas y agrupa TODOS los archivos relevantes (PDF, Excel, IMG, CSV).
    """
    if not os.path.isdir(root_dir):
        return [], f"Error: El directorio '{root_dir}' no existe."
    
    bundles = []
    errors = []
    
    # Extensiones permitidas
    valid_extensions = {
        '.pdf', '.csv', '.xlsx', '.xls', '.txt', 
        '.png', '.jpg', '.jpeg', '.tiff', '.gif',
        '.docx', '.doc'
    }
    
    for item in sorted(os.listdir(root_dir)):
        folder_path = os.path.join(root_dir, item)
        if os.path.isdir(folder_path):
            
            folder_files = []
            for f in os.listdir(folder_path):
                ext = os.path.splitext(f)[1].lower()
                if ext in valid_extensions:
                    full_path = os.path.join(folder_path, f)
                    folder_files.append(full_path)
            
            if folder_files:
                bundles.append({
                    'article_name': item,
                    'files': sorted(folder_files)
                })
            else:
                errors.append(f"⚠️ '{item}': Sin archivos válidos")

    if not bundles:
        errors.append("No se encontraron carpetas con archivos válidos.")
        
    return bundles, "\n".join(errors)

# --- PAGE CONFIG ---
st.set_page_config(layout="wide", page_title="Deep-Enzyme Agent - Multimodal")

st.title("🔎 Deep-Enzyme Forensic Auditor (Multimodal)")

# Sidebar
st.sidebar.header("Configuración")
api_key = st.sidebar.text_input("Gemini API Key", type="password", value=os.environ.get("GEMINI_API_KEY", ""))

if api_key:
    configure_genai(api_key)
    os.environ["GEMINI_API_KEY"] = api_key 

# --- TABS ---
tab1, tab2 = st.tabs(["📂 Modo Individual", "🚀 Procesamiento Masivo Multimodal"])

# ==========================================
# TAB 1: MODO INDIVIDUAL
# ==========================================
with tab1:
    st.header("Análisis de Artículo Individual")
    st.info("Sube todos los archivos de un artículo: PDF principal, suplementarios, Excels, CSVs, imágenes.")
    
    uploaded_files = st.file_uploader(
        "Archivos del Artículo", 
        type=["pdf", "xlsx", "xls", "csv", "png", "jpg", "jpeg", "txt"],
        accept_multiple_files=True
    )

    if uploaded_files:
        cleanup_temp_files()
        
        # Guardar archivos temporales
        temp_paths = []
        for uf in uploaded_files:
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uf.name)[1]) as f:
                f.write(uf.getbuffer())
                temp_paths.append(f.name)
                st.session_state['temp_files'].append(f.name)
        
        st.success(f"📦 {len(temp_paths)} archivos listos para análisis")
        
        # Mostrar lista de archivos
        for uf in uploaded_files:
            st.caption(f"• {uf.name}")
        
        if st.button("🔬 Analizar Paquete de Evidencia", type="primary", key="btn_individual"):
            if not api_key:
                st.error("Por favor configura la API Key.")
            else:
                with st.spinner("Ejecutando Auditoría Multimodal con Gemini 3..."):
                    try:
                        result: ExtractionResult = extract_catalytic_data(temp_paths)
                        st.session_state['data'] = result.model_dump()
                        st.success("✅ Auditoría completada.")
                    except Exception as e:
                        st.error(f"Error: {e}")

        if 'data' in st.session_state:
            st.markdown("### Resultados")
            df_flat = flatten_data_to_csv(ExtractionResult(**st.session_state['data']))
            st.dataframe(df_flat, use_container_width=True)
            
            csv = df_flat.to_csv(index=False).encode('utf-8')
            st.download_button("📄 Descargar CSV", data=csv, file_name="extraction.csv", mime="text/csv")
            
            # Mostrar figuras que requieren digitalización
            result_data = st.session_state['data']
            if result_data.get('figures_requiring_digitization'):
                st.markdown("### 📊 Figuras que Requieren Digitalización Manual")
                st.warning("Las siguientes figuras contienen datos relevantes que no pudieron extraerse automáticamente.")
                for fig in result_data['figures_requiring_digitization']:
                    with st.expander(f"📈 {fig['figure_id']} (Pág. {fig['page_number']})"):
                        st.write(f"**Descripción:** {fig['description']}")
                        st.write(f"**Tipo de datos:** {fig['data_type']}")
                        st.write(f"**Relevancia:** {fig['why_relevant']}")
                        if fig.get('estimated_datapoints'):
                            st.write(f"**Puntos estimados:** ~{fig['estimated_datapoints']}")

# ==========================================
# TAB 2: MODO MASIVO MULTIMODAL
# ==========================================
with tab2:
    st.header("🏭 Procesamiento Masivo Multimodal")
    st.markdown("""
    **Estructura esperada:**
    ```
    /Carpeta_Raiz/
      /Articulo_1/
        paper.pdf
        supplementary.pdf
        raw_data.xlsx
        gel_image.png
      /Articulo_2/
        ...
    ```
    """)

    root_directory = st.text_input(
        "Ruta ABSOLUTA a la Carpeta Raíz", 
        value="", 
        placeholder="/Users/usuario/Documents/Articulos"
    )
    
    bundles = []
    scan_errors = ""
    
    if root_directory and os.path.exists(root_directory):
        bundles, scan_errors = find_article_bundles(root_directory)
        
        if bundles:
            st.success(f"✅ Encontrados **{len(bundles)}** artículos/carpetas")
            
            # Preview table
            preview_data = []
            for b in bundles:
                file_types = list(set([os.path.splitext(f)[1].lower() for f in b['files']]))
                preview_data.append({
                    "Carpeta": b['article_name'], 
                    "Archivos": len(b['files']),
                    "Tipos": ", ".join(file_types)
                })
            st.dataframe(pd.DataFrame(preview_data), use_container_width=True, height=min(300, 35*len(bundles) + 38))
        
        if scan_errors:
            st.warning(scan_errors)
    
    elif root_directory:
        st.error(f"El directorio '{root_directory}' no existe.")

    if bundles and st.button("🔥 INICIAR ANÁLISIS MULTIMODAL COMPLETO", type="primary", key="btn_batch"):
        if not api_key:
            st.error("Configura la API Key primero.")
            st.stop()

        progress_bar = st.progress(0)
        status_text = st.empty()
        table_placeholder = st.empty()
        
        metric_col1, metric_col2, metric_col3 = st.columns(3)
        m1 = metric_col1.empty()
        m2 = metric_col2.empty()
        m3 = metric_col3.empty()
        
        master_df = pd.DataFrame()
        error_log = []  # Lista para registrar errores detallados
        total = len(bundles)
        success_count = 0
        errors_count = 0
        
        for i, bundle in enumerate(bundles):
            article_name = bundle['article_name']
            files = bundle['files']
            
            progress_bar.progress((i + 1) / total)
            status_text.markdown(f"**Procesando ({i+1}/{total}):** `{article_name}` ({len(files)} archivos)")

            try:
                # LLAMADA AL BACKEND MULTIMODAL
                extraction_result = extract_catalytic_data(files)
                df_chunk = flatten_data_to_csv(extraction_result)
                df_chunk["source_folder"] = article_name
                
                master_df = pd.concat([master_df, df_chunk], ignore_index=True)
                success_count += 1

                # Live update
                table_placeholder.dataframe(master_df.tail(10), use_container_width=True)
                m1.metric("Procesados", f"{i+1}/{total}")
                m2.metric("Datos Extraídos", len(master_df))
                m3.metric("Errores", errors_count)

            except Exception as e:
                errors_count += 1
                error_detail = {
                    "articulo": article_name,
                    "archivos": len(files),
                    "error_tipo": type(e).__name__,
                    "error_mensaje": str(e)
                }
                error_log.append(error_detail)
                m3.metric("Errores", errors_count)
                st.toast(f"Error en {article_name}: {str(e)[:100]}", icon="❌")

        status_text.empty()
        st.success(f"✅ ¡Procesamiento Completado! {success_count}/{total} exitosos.")
        
        # --- SECCIÓN DE RESULTADOS ---
        if not master_df.empty:
            st.markdown("### Base de Datos Completa")
            st.dataframe(master_df, use_container_width=True)
            
            csv = master_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar Base de Datos Completa (CSV)",
                data=csv,
                file_name="enzyme_database_multimodal.csv",
                mime="text/csv",
                type="primary"
            )
        
        # --- SECCIÓN DE ERRORES ---
        if error_log:
            st.markdown("### ❌ Registro de Errores")
            st.warning(f"Se encontraron {len(error_log)} errores durante el procesamiento.")
            
            # Mostrar tabla de errores
            df_errors = pd.DataFrame(error_log)
            st.dataframe(df_errors, use_container_width=True)
            
            # Descargar log de errores
            error_csv = df_errors.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar Log de Errores (CSV)",
                data=error_csv,
                file_name="error_log.csv",
                mime="text/csv"
            )
            
            # Expandible con detalles completos
            with st.expander("Ver detalles completos de errores"):
                for err in error_log:
                    st.error(f"**{err['articulo']}** ({err['archivos']} archivos)")
                    st.code(f"Tipo: {err['error_tipo']}\nMensaje: {err['error_mensaje']}")
