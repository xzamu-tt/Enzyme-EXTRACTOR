import streamlit as st
import os
import json
import tempfile
import base64
from dotenv import load_dotenv

# Try to load from .env
load_dotenv()

# Add parent directory to path to ensure imports work
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.backend import extract_catalytic_data, merge_pdfs, configure_genai, flatten_data_to_csv
    from src.models import ExtractionResult, EnzymeVariant, ActivityExperiment, Evidence
except ImportError as e:
    st.error(f"Error importando módulos backend: {e}")

st.set_page_config(layout="wide", page_title="Deep-Enzyme Agent - Forensic Mode")

st.title("🔎 Deep-Enzyme Forensic Auditor")

# Sidebar
st.sidebar.header("Configuración")
api_key = st.sidebar.text_input("Gemini API Key", type="password", value=os.environ.get("GEMINI_API_KEY", ""))

if api_key:
    configure_genai(api_key)
    # Update env for deep usage if needed in sub-calls relying on env
    os.environ["GEMINI_API_KEY"] = api_key 

st.sidebar.header("Documentos")
main_pdf = st.sidebar.file_uploader("Paper Principal (PDF)", type="pdf")
supp_pdf = st.sidebar.file_uploader("Material Suplementario (PDF, Opcional)", type="pdf")

if main_pdf:
    # Save temp
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
        f.write(main_pdf.getbuffer())
        main_pdf_path = f.name
    
    final_pdf_path = main_pdf_path
    
    if supp_pdf:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f_supp:
            f_supp.write(supp_pdf.getbuffer())
            supp_pdf_path = f_supp.name
        
        # Merge
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f_merged:
            merged_path = f_merged.name
        
        with st.spinner("Fusionando documentos..."):
            final_pdf_path = merge_pdfs(main_pdf_path, supp_pdf_path, merged_path)
            st.sidebar.success("Documentos fusionados.")

    # Layout
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Visualizador")
        # Iframe for PDF using base64
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

        # Editable form
        if 'data' in st.session_state:
            st.markdown("### Resultados de Auditoría")
            
            # Allow editing DOI
            paper_doi = st.text_input("DOI", value=st.session_state['data'].get("paper_doi") or "")
            st.session_state['data']['paper_doi'] = paper_doi

            variants = st.session_state['data'].get('variants', [])
            
            for i, variant in enumerate(variants):
                # Enzyme Variant Header
                variant_label = f"Enzima {i+1}: {variant.get('sample_id', 'Unknown')}"

                with st.expander(variant_label, expanded=True if i==0 else False):
                    # 1. Variant Details (Level 2)
                    st.markdown("#### Datos de Variante (Comunes a todas las mediciones)")
                    c1, c2 = st.columns(2)
                    variant['sample_id'] = c1.text_input("ID Muestra", variant.get('sample_id'), key=f"id_{i}")
                    variant['expression_mg_ml'] = c2.number_input("Expresión (mg/mL)", value=float(variant.get('expression_mg_ml') or 0.0), key=f"expr_{i}")

                    c3, c4 = st.columns(2)
                    variant['tm_c'] = c3.number_input("Tm (°C)", value=float(variant.get('tm_c') or 0.0), key=f"tm_{i}")
                    
                    # Sequences
                    variant['seq_aa'] = st.text_area("Secuencia AA", value=variant.get('seq_aa', ""), height=100, key=f"seq_aa_{i}")
                    variant['seq_nuc'] = st.text_area("Secuencia Nuc", value=variant.get('seq_nuc', "") or "", height=70, key=f"seq_nuc_{i}")

                    # 2. Activities List (Level 1)
                    st.divider()
                    st.markdown("#### Lista de Mediciones Auditas")
                    measurements = variant.get('measurements', [])
                    
                    for j, meas in enumerate(measurements):
                        
                        # Layout: Data on Left, Evidence on Right
                        mc_cols = st.columns([1.5, 1])
                        
                        with mc_cols[0]: # Data Inputs
                            st.caption(f"Medición {j+1} - Datos")
                            d1, d2 = st.columns(2)
                            meas['time_h'] = d1.number_input("Tiempo (h)", value=float(meas.get('time_h', 0.0)), key=f"m_t_{i}_{j}")
                            meas['ph'] = d2.number_input("pH", value=float(meas.get('ph', 7.0)), key=f"m_ph_{i}_{j}")
                            
                            d3, d4 = st.columns(2)
                            meas['temperature_c'] = d3.number_input("Temp (°C)", value=float(meas.get('temperature_c', 30.0)), key=f"m_temp_{i}_{j}")
                            meas['substrate'] = d4.text_input("Sustrato", value=meas.get('substrate', ""), key=f"m_sub_{i}_{j}")
                        
                            meas['mM_product_per_mg_enzyme'] = st.number_input("mM/mg (Val)", value=float(meas.get('mM_product_per_mg_enzyme', 0.0)), key=f"m_norm_{i}_{j}")
                        
                        with mc_cols[1]: # Evidence Display
                            st.caption("🧾 Evidencia Forense")
                            evidence = meas.get('evidence', {})
                            
                            # Confidence Indicator
                            conf = evidence.get('confidence_score', 0.0)
                            if conf > 0.9:
                                st.success(f"Confianza Alta: {conf}")
                            elif conf > 0.5:
                                st.warning(f"Confianza Media: {conf}")
                            else:
                                st.error(f"Confianza Baja: {conf}")

                            st.info(f"Página: {evidence.get('page_number', '?')} ({evidence.get('location_type', '?')})")
                            st.text_area("Snippet Original (Copia Literal)", value=evidence.get('raw_text_snippet', ""), height=100, key=f"ev_snip_{i}_{j}", disabled=True)
                        
                        meas['evidence'] = evidence
                        st.divider()

                    if st.button(f"Añadir Medición a {variant.get('sample_id')}", key=f"add_meas_{i}"):
                        # Add empty structure with empty evidence
                        measurements.append({
                            "time_h": 24.0, "ph": 7.0, "temperature_c": 30.0, 
                            "substrate": "PET", "mM_product": 0.0, "mM_product_per_mg_enzyme": 0.0,
                            "evidence": {"raw_text_snippet": "", "page_number": 0, "location_type": "Manual", "confidence_score": 1.0}
                        })
                        st.rerun()
                    
                    variant['measurements'] = measurements

            # Export Section
            st.markdown("### Exportación")
            col_exp1, col_exp2 = st.columns(2)
            
            with col_exp1:
                # Convert back to Pydantic for validation/logic
                try:
                    # Reconstruct object
                    current_extraction = ExtractionResult(paper_doi=st.session_state['data'].get("paper_doi"), variants=variants)
                    
                    # Flatten
                    df_flat = flatten_data_to_csv(current_extraction)
                    csv = df_flat.to_csv(index=False).encode('utf-8')
                    
                    st.download_button(
                        label="📄 Descargar CSV Auditado",
                        data=csv,
                        file_name="audit_data_flattened.csv",
                        mime="text/csv",
                        type="primary"
                    )
                except Exception as e:
                    st.error(f"Error generando CSV: {e}")

            with col_exp2:
                final_json = json.dumps(st.session_state['data'], indent=2)
                st.download_button("Descargar JSON Forense", data=final_json, file_name="forensic_data.json", mime="application/json")
