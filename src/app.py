import streamlit as st
import os
import json
import tempfile
import base64
import atexit
from dotenv import load_dotenv

# Try to load from .env
load_dotenv()

# Add parent directory to path to ensure imports work
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.backend import extract_catalytic_data, merge_pdfs, configure_genai, flatten_data_to_csv
    from src.models import ExtractionResult, EnzymeVariant, ActivityExperiment, Evidence, KineticParameter
except ImportError as e:
    st.error(f"Error importando módulos backend: {e}")

# --- Temp File Cleanup ---
if 'temp_files' not in st.session_state:
    st.session_state['temp_files'] = []

def cleanup_temp_files():
    """Remove all tracked temporary files."""
    for path in st.session_state.get('temp_files', []):
        try:
            if os.path.exists(path):
                os.remove(path)
                print(f"Cleaned up temp file: {path}")
        except Exception as e:
            print(f"Warning: Could not delete temp file {path}: {e}")
    st.session_state['temp_files'] = []

atexit.register(cleanup_temp_files)

st.set_page_config(layout="wide", page_title="Deep-Enzyme Agent - Forensic Mode")

st.title("🔎 Deep-Enzyme Forensic Auditor")

# Sidebar
st.sidebar.header("Configuración")
api_key = st.sidebar.text_input("Gemini API Key", type="password", value=os.environ.get("GEMINI_API_KEY", ""))

if api_key:
    configure_genai(api_key)
    os.environ["GEMINI_API_KEY"] = api_key 

st.sidebar.header("Documentos")
main_pdf = st.sidebar.file_uploader("Paper Principal (PDF)", type="pdf")
supp_pdf = st.sidebar.file_uploader("Material Suplementario (PDF, Opcional)", type="pdf")

if st.sidebar.button("🧹 Limpiar Archivos Temporales"):
    cleanup_temp_files()
    st.sidebar.success("Archivos temporales eliminados.")

if main_pdf:
    cleanup_temp_files()
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
        f.write(main_pdf.getbuffer())
        main_pdf_path = f.name
        st.session_state['temp_files'].append(main_pdf_path)
    
    final_pdf_path = main_pdf_path
    
    if supp_pdf:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f_supp:
            f_supp.write(supp_pdf.getbuffer())
            supp_pdf_path = f_supp.name
            st.session_state['temp_files'].append(supp_pdf_path)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f_merged:
            merged_path = f_merged.name
            st.session_state['temp_files'].append(merged_path)
        
        with st.spinner("Fusionando documentos..."):
            final_pdf_path = merge_pdfs(main_pdf_path, supp_pdf_path, merged_path)
            st.sidebar.success("Documentos fusionados.")

    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Visualizador")
        with open(final_pdf_path, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode('utf-8')
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800" type="application/pdf"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)

    with col2:
        st.subheader("Extracción Forense")
        
        if st.button("Auditar Datos (Extracción + Evidencia)", type="primary"):
            if not api_key:
                st.error("Por favor configura la API Key.")
            else:
                with st.spinner("Ejecutando Auditoría Forense con Gemini..."):
                    try:
                        result: ExtractionResult = extract_catalytic_data(final_pdf_path)
                        st.session_state['data'] = result.model_dump()
                        st.success("Auditoría completada.")
                    except Exception as e:
                        st.error(f"Error durante la auditoría: {e}")

        if 'data' in st.session_state:
            st.markdown("### Resultados de Auditoría")
            
            paper_doi = st.text_input("DOI", value=st.session_state['data'].get("paper_doi") or "")
            st.session_state['data']['paper_doi'] = paper_doi

            variants = st.session_state['data'].get('variants', [])
            
            for i, variant in enumerate(variants):
                variant_label = f"Enzima {i+1}: {variant.get('sample_id', 'Unknown')}"

                with st.expander(variant_label, expanded=True if i==0 else False):
                    st.markdown("#### Datos de Variante")
                    c1, c2 = st.columns(2)
                    variant['sample_id'] = c1.text_input("ID Muestra", variant.get('sample_id'), key=f"id_{i}")
                    variant['expression_mg_ml'] = c2.number_input("Expresión (mg/mL)", value=float(variant.get('expression_mg_ml') or 0.0), key=f"expr_{i}")

                    c3, c4 = st.columns(2)
                    variant['tm_c'] = c3.number_input("Tm (°C)", value=float(variant.get('tm_c') or 0.0), key=f"tm_{i}")
                    
                    variant['seq_aa'] = st.text_area("Secuencia AA", value=variant.get('seq_aa', ""), height=80, key=f"seq_aa_{i}")
                    variant['seq_nuc'] = st.text_area("Secuencia Nuc", value=variant.get('seq_nuc', "") or "", height=60, key=f"seq_nuc_{i}")

                    st.divider()
                    st.markdown("#### Mediciones")
                    measurements = variant.get('measurements', [])
                    
                    for j, meas in enumerate(measurements):
                        st.markdown(f"**Medición {j+1}**")
                        
                        # Substrate metadata
                        sub_cols = st.columns(3)
                        meas['substrate_name'] = sub_cols[0].text_input("Sustrato", meas.get('substrate_name', ''), key=f"sub_{i}_{j}")
                        meas['substrate_morphology'] = sub_cols[1].text_input("Morfología", meas.get('substrate_morphology', ''), key=f"morph_{i}_{j}")
                        meas['substrate_crystallinity_pct'] = sub_cols[2].number_input("Cristalinidad (%)", value=float(meas.get('substrate_crystallinity_pct') or 0.0), key=f"cryst_{i}_{j}")
                        
                        # Conditions
                        cond_cols = st.columns(3)
                        meas['time_h'] = cond_cols[0].number_input("Tiempo (h)", value=float(meas.get('time_h') or 0.0), key=f"time_{i}_{j}")
                        meas['temperature_c'] = cond_cols[1].number_input("Temp (°C)", value=float(meas.get('temperature_c', 30.0)), key=f"temp_{i}_{j}")
                        meas['ph'] = cond_cols[2].number_input("pH", value=float(meas.get('ph', 7.0)), key=f"ph_{i}_{j}")
                        
                        # Dynamic Metrics Editor
                        st.markdown("**Métricas Cinéticas Reportadas:**")
                        metrics = meas.get('reported_metrics', [])
                        
                        if metrics:
                            metrics_data = [m if isinstance(m, dict) else m for m in metrics]
                            edited_metrics = st.data_editor(
                                metrics_data,
                                num_rows="dynamic",
                                key=f"metrics_{i}_{j}",
                                column_config={
                                    "type": st.column_config.SelectboxColumn(
                                        "Tipo",
                                        options=["kcat", "Km", "Vmax", "SpecificActivity", "ProductConcentration", "Conversion", "HalfLife", "Other"],
                                        width="medium"
                                    ),
                                    "value": st.column_config.NumberColumn("Valor", format="%.4f"),
                                    "unit": st.column_config.TextColumn("Unidad"),
                                    "standard_deviation": st.column_config.NumberColumn("Std Dev", format="%.4f")
                                },
                                use_container_width=True
                            )
                            meas['reported_metrics'] = edited_metrics
                        else:
                            st.warning("No se detectaron métricas cinéticas.")
                            if st.button(f"Añadir Métrica Manual", key=f"add_metric_{i}_{j}"):
                                meas['reported_metrics'] = [{"type": "Other", "value": 0.0, "unit": "", "standard_deviation": None}]
                                st.rerun()
                        
                        # Evidence Display
                        st.markdown("**🧾 Evidencia:**")
                        evidence = meas.get('evidence', {})
                        ev_cols = st.columns([1, 1, 2])
                        conf = evidence.get('confidence_score', 0.0)
                        if conf > 0.9:
                            ev_cols[0].success(f"Confianza: {conf}")
                        elif conf > 0.5:
                            ev_cols[0].warning(f"Confianza: {conf}")
                        else:
                            ev_cols[0].error(f"Confianza: {conf}")
                        ev_cols[1].info(f"Pág: {evidence.get('page_number', '?')}")
                        ev_cols[2].caption(f"Tipo: {evidence.get('location_type', '?')}")
                        
                        st.text_area("Snippet Original", value=evidence.get('raw_text_snippet', ""), height=60, key=f"snip_{i}_{j}", disabled=True)
                        
                        meas['evidence'] = evidence
                        st.divider()

                    if st.button(f"Añadir Medición", key=f"add_meas_{i}"):
                        measurements.append({
                            "time_h": 24.0, "ph": 7.0, "temperature_c": 30.0, 
                            "substrate_name": "PET", "substrate_morphology": "film", "substrate_crystallinity_pct": None,
                            "reported_metrics": [{"type": "ProductConcentration", "value": 0.0, "unit": "mM", "standard_deviation": None}],
                            "evidence": {"raw_text_snippet": "", "page_number": 0, "location_type": "Manual", "confidence_score": 1.0}
                        })
                        st.rerun()
                    
                    variant['measurements'] = measurements

            st.markdown("### Exportación")
            col_exp1, col_exp2 = st.columns(2)
            
            with col_exp1:
                try:
                    current_extraction = ExtractionResult(paper_doi=st.session_state['data'].get("paper_doi"), variants=variants)
                    df_flat = flatten_data_to_csv(current_extraction)
                    csv = df_flat.to_csv(index=False).encode('utf-8')
                    
                    st.download_button(
                        label="📄 Descargar CSV (Tidy Format)",
                        data=csv,
                        file_name="enzyme_data_tidy.csv",
                        mime="text/csv",
                        type="primary"
                    )
                except Exception as e:
                    st.error(f"Error generando CSV: {e}")

            with col_exp2:
                final_json = json.dumps(st.session_state['data'], indent=2)
                st.download_button("Descargar JSON Forense", data=final_json, file_name="forensic_data.json", mime="application/json")
