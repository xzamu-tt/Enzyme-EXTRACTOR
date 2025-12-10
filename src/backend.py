import os
import time
import mimetypes
import pandas as pd
import google.generativeai as genai
from src.models import ExtractionResult, PaperExtraction

def configure_genai(api_key: str):
    genai.configure(api_key=api_key)

def _handle_excel_file(file_path: str) -> str:
    """
    Convierte Excel a CSV/texto para máxima precisión de lectura por Gemini.
    """
    try:
        xls = pd.ExcelFile(file_path)
        all_sheets = []
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            csv_str = f"--- SHEET: {sheet_name} ---\n" + df.to_csv(index=False)
            all_sheets.append(csv_str)
        
        combined_csv_path = file_path + "_converted.txt"
        with open(combined_csv_path, "w", encoding="utf-8") as f:
            f.write("\n\n".join(all_sheets))
        
        return combined_csv_path
    except Exception as e:
        print(f"Error convirtiendo Excel {file_path}: {e}")
        return file_path

def extract_catalytic_data(file_paths: list) -> ExtractionResult:
    """
    Extrae datos de un PAQUETE de archivos multimodal (PDFs, Excels, CSVs, Imágenes).
    """
    uploaded_files = []
    converted_files_to_cleanup = []

    print(f"📦 Preparando paquete con {len(file_paths)} archivos...")

    try:
        # 1. SUBIDA DE ARCHIVOS (Multimodal Loop)
        for path in file_paths:
            mime_type, _ = mimetypes.guess_type(path)
            
            # Manejo especial para Excel -> Convertir a Texto/CSV
            if path.lower().endswith(('.xlsx', '.xls')):
                print(f"   🔄 Convirtiendo Excel: {os.path.basename(path)}")
                path = _handle_excel_file(path)
                converted_files_to_cleanup.append(path)
                mime_type = "text/plain"

            # Manejo de CSVs
            if path.lower().endswith('.csv'):
                mime_type = "text/csv"

            # Default mime type si no se detecta
            if not mime_type:
                mime_type = "application/octet-stream"

            print(f"   ⬆️ Subiendo: {os.path.basename(path)} ({mime_type})...")
            
            file_ref = genai.upload_file(path, mime_type=mime_type)
            uploaded_files.append(file_ref)

        # 2. ESPERA ACTIVA (Processing check)
        print("   ⏳ Verificando procesamiento en la nube...")
        active_files = []
        for f in uploaded_files:
            while f.state.name == "PROCESSING":
                time.sleep(1)
                f = genai.get_file(f.name)
            
            if f.state.name == "FAILED":
                print(f"   ❌ Falló archivo: {f.name}. Se omitirá.")
            else:
                active_files.append(f)

        if not active_files:
            raise ValueError("Ningún archivo se pudo procesar correctamente.")

        # 3. CONFIGURACIÓN DEL MODELO (SIN response_schema para evitar errores)
        generation_config = {
            "temperature": 1.0,
            "response_mime_type": "application/json"
            # NO usamos response_schema - parseamos manualmente con Pydantic
        }
        
        model = genai.GenerativeModel(
            model_name="gemini-3-pro-preview",
            generation_config=generation_config
        )

        # 4. PROMPT MULTIMODAL EXHAUSTIVO CON SCHEMA EXPLÍCITO
        system_prompt = """
        ROL: Auditor Forense Multimodal de Datos Masivos (PDF + Excel + Imágenes + CSV).
        
        CONTEXTO:
        Se te ha entregado un "Paquete de Evidencia" que puede contener:
        1. Artículo Principal (PDF)
        2. Material Suplementario (PDF/Word)
        3. Datos Crudos (Excel, CSV)
        4. Evidencia Visual (Imágenes de geles, gráficos)

        TU MISIÓN:
        Analizar TODO el conjunto y extraer datos de actividad enzimática CON METADATOS COMPLETOS para normalización.

        REGLAS ESTRICTAS:
        1. PROHIBIDO RESUMIR: Extrae TODAS las variantes.
        2. MULTI-FUENTE: Cruza información entre PDF y Excel.
        3. BÚSQUEDA PROFUNDA: Revisa TODOS los archivos.
        4. METADATOS CRÍTICOS: Sin volumen de reacción, carga de enzima y cantidad de sustrato, los datos no se pueden comparar.

        FORMATO DE SALIDA - JSON EXACTO:
        {
          "paper_doi": "10.xxxx/xxxx o null",
          "variants": [
            {
              "sample_id": "Nombre de la variante (ej: LCC-ICCG, Wild Type)",
              "seq_aa": "Secuencia de aminoácidos o null",
              "seq_nuc": "Secuencia nucleótidos o null",
              "expression_value": 1.5 o null,
              "expression_unit": "mg/mL, mg/L, g/L, µg/mL o null",
              "tm_c": 65.0 o null,
              "measurements": [
                {
                  "time_h": 24.0 o null,
                  "temperature_c": 37.0 o null,
                  "ph": 7.5 o null,
                  
                  "reaction_volume_ml": 1.0 o null,
                  
                  "enzyme_loading_value": 0.5 o null,
                  "enzyme_loading_unit": "mg/mL, nM, µM, mg enzyme/g PET, etc. o null",
                  
                  "substrate_name": "PET o null",
                  "substrate_morphology": "film, powder, etc. o null",
                  "substrate_crystallinity_pct": 30.0 o null,
                  "substrate_amount_value": 10.0 o null,
                  "substrate_amount_unit": "mg, g, mg/mL, etc. o null",
                  
                  "product_yield_raw": "DATO CRUDO TAL CUAL: ej '15.2 µg/mg PET', '45% conversion', '2.3 mM TPA'",
                  "product_yield_unit": "La unidad si se puede separar o null",
                  
                  "reported_metrics": [
                    {
                      "type": "kcat, Km, Vmax, SpecificActivity, Conversion, HalfLife, Other",
                      "value": 10.5,
                      "unit": "s-1, mM, %, etc.",
                      "standard_deviation": 0.5 o null
                    }
                  ],
                  "evidence": {
                    "raw_text_snippet": "Texto LITERAL copiado del documento",
                    "page_number": 5,
                    "location_type": "Table 1, Figure 2, Excel Sheet 1",
                    "confidence_score": 0.95
                  }
                }
              ]
            }
          ]
        }

        INSTRUCCIONES ADICIONALES:
        - PRODUCT YIELD: Copia el dato de producto/yield EXACTAMENTE como aparece (ej: "15.2 µg/mg PET", "45% conversion").
        - EXPRESIÓN: Busca en CUALQUIER unidad (mg/mL, mg/L, g/L).
        - CARGA DE ENZIMA: Busca "enzyme loading", "enzyme concentration".
        - CANTIDAD DE SUSTRATO: Busca cantidades en mg o g.
        - VOLUMEN: Busca "reaction volume", valores en mL.
        
        RESPONDE SOLO CON EL JSON, SIN TEXTO ADICIONAL.
        """

        # 5. GENERACIÓN
        print("   🧠 Analizando paquete multimodal...")
        try:
            response = model.generate_content(active_files + [system_prompt])
        except Exception as gen_error:
            print(f"   ❌ ERROR EN GENERACIÓN: {type(gen_error).__name__}")
            print(f"   ❌ MENSAJE: {str(gen_error)}")
            import traceback
            traceback.print_exc()
            raise gen_error
        
        if not response.parts:
            feedback = getattr(response, 'prompt_feedback', 'Sin información')
            print(f"   ❌ RESPUESTA BLOQUEADA: {feedback}")
            raise ValueError(f"Gemini bloqueó la respuesta: {feedback}")

        # 6. PARSEAR JSON MANUALMENTE
        if not response.text:
            raise ValueError("Gemini devolvió respuesta vacía.")
        
        try:
            # Parsear con Pydantic directamente
            result = ExtractionResult.model_validate_json(response.text)
            print(f"   ✅ Extracción exitosa: {len(result.variants)} variantes encontradas")
            return result
        except Exception as parse_error:
            print(f"   ❌ ERROR PARSEANDO JSON: {type(parse_error).__name__}")
            print(f"   ❌ MENSAJE: {str(parse_error)}")
            print(f"   📄 Respuesta raw (primeros 1000 chars):\n{response.text[:1000]}")
            raise ValueError(f"Error parseando respuesta: {parse_error}")

    finally:
        # 6. LIMPIEZA OBLIGATORIA
        print("   🧹 Limpiando archivos en la nube...")
        for f in uploaded_files:
            try:
                f.delete()
            except:
                pass
        
        for local_path in converted_files_to_cleanup:
            if os.path.exists(local_path):
                os.remove(local_path)


def flatten_data_to_csv(extraction_result: PaperExtraction) -> pd.DataFrame:
    """
    Aplana los datos jerárquicos a formato CSV Wide.
    """
    rows = []
    
    if not extraction_result.variants:
        return pd.DataFrame()

    for variant in extraction_result.variants:
        common_data = {
            "sample_id": variant.sample_id,
            "seq_aa": variant.seq_aa,
            "seq_nuc": variant.seq_nuc,
            "expression_value": variant.expression_value,
            "expression_unit": variant.expression_unit,
            "tm_c": variant.tm_c
        }
        
        for meas in variant.measurements:
            row = common_data.copy()
            
            row.update({
                "time_h": meas.time_h,
                "temperature_c": meas.temperature_c,
                "pH": meas.ph,
                
                # Metadatos para normalización
                "reaction_volume_ml": meas.reaction_volume_ml,
                "enzyme_loading_value": meas.enzyme_loading_value,
                "enzyme_loading_unit": meas.enzyme_loading_unit,
                
                # Sustrato
                "substrate": meas.substrate_name,
                "substrate_morphology": meas.substrate_morphology,
                "crystallinity_pct": meas.substrate_crystallinity_pct,
                "substrate_amount_value": meas.substrate_amount_value,
                "substrate_amount_unit": meas.substrate_amount_unit,
                
                # Product Yield crudo
                "product_yield_raw": meas.product_yield_raw,
                "product_yield_unit": meas.product_yield_unit,
                
                # Evidencia
                "evidence_page": meas.evidence.page_number,
                "evidence_confidence": meas.evidence.confidence_score,
                "evidence_snippet": meas.evidence.raw_text_snippet,
                "evidence_location": meas.evidence.location_type
            })

            # Pivote: Cada métrica es una columna
            for metric in meas.reported_metrics:
                col_name = metric.type
                row[col_name] = metric.value
                row[f"{col_name}_unit"] = metric.unit
                if metric.standard_deviation:
                    row[f"{col_name}_std"] = metric.standard_deviation
                
            rows.append(row)
            
    df = pd.DataFrame(rows)
    
    # Ordenamiento de columnas
    desired_order = [
        "sample_id", "time_h", "substrate", "substrate_morphology", "crystallinity_pct",
        "temperature_c", "pH",
        "ProductConcentration", "ProductConcentration_unit",
        "SpecificActivity", "SpecificActivity_unit",
        "kcat", "kcat_unit", "Km", "Km_unit",
        "Conversion", "Conversion_unit",
        "expression_mg_ml", "tm_c",
        "seq_aa", "seq_nuc",
        "evidence_page", "evidence_location", "evidence_confidence", "evidence_snippet"
    ]
    
    final_cols = [c for c in desired_order if c in df.columns] + [c for c in df.columns if c not in desired_order]
    
    return df[final_cols]
