import os
import time
import google.generativeai as genai
from pypdf import PdfWriter
from src.models import ExtractionResult, PaperExtraction
import pandas as pd

def configure_genai(api_key: str):
    genai.configure(api_key=api_key)

def merge_pdfs(main_pdf_path: str, supp_pdf_path: str | None, output_path: str) -> str:
    """Combina el PDF principal y el suplementario en un solo archivo."""
    if not supp_pdf_path:
        return main_pdf_path
        
    merger = PdfWriter()
    merger.append(main_pdf_path)
    if supp_pdf_path:
        merger.append(supp_pdf_path)
    
    merger.write(output_path)
    merger.close()
    return output_path

def extract_catalytic_data(pdf_path: str, mime_type="application/pdf") -> ExtractionResult:
    """
    Extrae datos catalíticos de un PDF usando Gemini.
    Incluye manejo robusto de recursos y errores.
    """
    # 1. Cargar archivo
    print(f"Subiendo archivo {pdf_path} a Gemini...")
    file_ref = genai.upload_file(pdf_path, mime_type=mime_type)
    print(f"Archivo subido: {file_ref.name}")
    
    try:
        # 2. Esperar a que el archivo esté procesado (para archivos grandes)
        while file_ref.state.name == "PROCESSING":
            print("Procesando archivo en servidor...")
            time.sleep(2)
            file_ref = genai.get_file(file_ref.name)

        if file_ref.state.name == "FAILED":
            raise ValueError("Falló el procesamiento del archivo en Gemini.")
        
        # 3. Configurar el modelo con el esquema Pydantic
        generation_config = {
            "temperature": 0.0, # Determinístico
            "response_mime_type": "application/json",
            "response_schema": ExtractionResult
        }
        
        model = genai.GenerativeModel(
            model_name="gemini-2.5-pro-preview-06-05", # Gemini 3 Pro (latest preview)
            generation_config=generation_config
        )

        # 4. NUEVO PROMPT ADAPTADO - Métricas Flexibles
        system_prompt = """
        ROL: Auditor Científico Senior para base de datos de ingeniería de enzimas.
        
        OBJETIVO: Extraer datos de actividad catalítica, expresión y estabilidad térmica (Tm).
        
        INSTRUCCIONES CRÍTICAS SOBRE MÉTRICAS CINÉTICAS:
        Los papers reportan actividad de muchas formas. Debes extraer TODAS las que encuentres para cada experimento:
        - Si reportan kcat y KM, extrae ambos como items separados en `reported_metrics`.
        - Si reportan concentración de producto (mM) o conversión (%), extráelo.
        - Si reportan Actividad Específica (U/mg), extráelo.
        - NO calcules ni conviertas unidades. Extrae el valor y la unidad TAL CUAL aparecen.
        - Usa el campo `type` para clasificar: 'kcat', 'Km', 'Vmax', 'SpecificActivity', 'ProductConcentration', 'Conversion', 'HalfLife', 'Other'.
        
        INSTRUCCIONES SOBRE SUSTRATOS:
        - Es VITAL identificar la morfología del sustrato (polvo, film, pastilla) usando `substrate_morphology`.
        - Si se menciona la cristalinidad (%), extráela en `substrate_crystallinity_pct`. Esto afecta la degradación de PET.
        
        INSTRUCCIONES SOBRE EXPRESIÓN Y TM:
        - Expresión: Busca valores en mg/mL (fracción soluble).
        - Tm: Busca valores de 'Melting Temperature' o Tm, frecuentemente medidos por DSF (Differential Scanning Fluorimetry).
        
        REGLA DE ORO DE EVIDENCIA:
        - Todo dato debe tener su 'raw_text_snippet' copiado LITERALMENTE del PDF.
        - Incluye el número de página y tipo de fuente (Table, Figure, Text).
        """

        # 5. Ejecutar extracción
        print("Iniciando extracción forense con Gemini...")
        response = model.generate_content([file_ref, system_prompt])
        
        # 6. Validar respuesta
        if not response.parts:
            feedback = getattr(response, 'prompt_feedback', 'Sin información adicional')
            raise ValueError(f"Gemini bloqueó la respuesta. Razón: {feedback}")

        if not response.parsed:
            raise ValueError("El modelo no devolvió un JSON válido compatible con el esquema.")

        return response.parsed
    
    finally:
        # SIEMPRE borrar el archivo remoto, incluso si hay error
        print(f"Eliminando archivo remoto: {file_ref.name}")
        try:
            file_ref.delete()
        except Exception as e:
            print(f"Advertencia: No se pudo eliminar el archivo remoto: {e}")

def flatten_data_to_csv(extraction_result: PaperExtraction) -> pd.DataFrame:
    """
    Aplana los datos jerárquicos a formato CSV.
    Genera formato "Wide" donde cada tipo de métrica es una columna separada.
    Esto coincide con el formato de activity_2025.csv.
    """
    rows = []
    
    if not extraction_result.variants:
        return pd.DataFrame()

    for variant in extraction_result.variants:
        # Datos fijos de la enzima (coincide con tm_expression_2025.csv)
        common_data = {
            "sample_id": variant.sample_id,
            "seq_aa": variant.seq_aa,
            "seq_nuc": variant.seq_nuc,
            "expression_mg_ml": variant.expression_mg_ml,
            "tm_c": variant.tm_c
        }
        
        for meas in variant.measurements:
            row = common_data.copy()
            
            # Metadatos del experimento (coincide con activity_2025.csv)
            row.update({
                "time_h": meas.time_h,
                "temperature_c": meas.temperature_c,
                "pH": meas.ph,
                "substrate": meas.substrate_name,
                "substrate_morphology": meas.substrate_morphology,
                "crystallinity_pct": meas.substrate_crystallinity_pct,
                
                # Evidencia para trazabilidad
                "evidence_page": meas.evidence.page_number,
                "evidence_confidence": meas.evidence.confidence_score,
                "evidence_snippet": meas.evidence.raw_text_snippet
            })

            # --- LÓGICA DE PIVOTE PARA FORMATO "WIDE" ---
            # Cada métrica encontrada se convierte en su propia columna
            for metric in meas.reported_metrics:
                col_name = metric.type
                row[col_name] = metric.value
                row[f"{col_name}_unit"] = metric.unit
                if metric.standard_deviation:
                    row[f"{col_name}_std"] = metric.standard_deviation
                
            rows.append(row)
            
    # Crear DataFrame
    df = pd.DataFrame(rows)
    
    # Reordenar columnas: Datos base primero, luego métricas dinámicas
    desired_order = [
        "sample_id", "time_h", "substrate", "substrate_morphology", "crystallinity_pct",
        "temperature_c", "pH",
        # Métricas comunes (si existen)
        "ProductConcentration", "ProductConcentration_unit",
        "SpecificActivity", "SpecificActivity_unit",
        "kcat", "kcat_unit", "Km", "Km_unit",
        "Conversion", "Conversion_unit",
        # Datos de enzima
        "expression_mg_ml", "tm_c",
        "seq_aa", "seq_nuc",
        # Trazabilidad al final
        "evidence_page", "evidence_confidence", "evidence_snippet"
    ]
    
    # Filtramos para usar solo las columnas que realmente existen + las nuevas que no previmos
    final_cols = [c for c in desired_order if c in df.columns] + [c for c in df.columns if c not in desired_order]
    
    return df[final_cols]

