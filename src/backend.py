import os
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
    # 1. Cargar archivo
    print(f"Subiendo archivo {pdf_path} a Gemini...")
    file_ref = genai.upload_file(pdf_path, mime_type=mime_type)
    print(f"Archivo subido: {file_ref.name}")
    
    # 2. Configurar el modelo con el esquema Pydantic
    generation_config = {
        "temperature": 0.0, # Determinístico
        "response_mime_type": "application/json",
        "response_schema": ExtractionResult
    }
    
    model = genai.GenerativeModel(
        model_name="gemini-1.5-pro", # Usando 1.5 Pro a petición del usuario para mejor handling
        generation_config=generation_config
    )

    # 3. Prompt de Sistema "Forensic Auditor"
    system_prompt = """
    ROL: Eres un auditor forense de datos científicos y experto en ingeniería de proteínas. Tu misión NO es solo extraer números, sino construir un CASO DE EVIDENCIA irrefutable.

    OBJETIVO: Extraer datos cinéticos para un torneo de biotecnología, con TRAZABILIDAD TOTAL.

    REGLAS DE EVIDENCIA (CRÍTICO - SI FALLAS AQUÍ, EL DATO SE DESCARTA):
    1. Para cada medición de actividad (`ActivityExperiment`), DEBES proporcionar la `evidence` completa.
    2. `raw_text_snippet`: Copia y pega EXACTAMENTE el fragmento de texto o la fila de la tabla de donde sacaste el número. Esto se usará para búsqueda automática (Ctrl+F), así que sé literal.
    3. `page_number`: Indica la página del PDF donde está el dato.
    4. `confidence_score`: Evalúa tu certeza (0.0 - 1.0). Si tuviste que asumir algo (ej. temperatura ambiente = 25C), baja el score.

    REGLAS DE EXTRACCIÓN JERÁRQUICA:
    1. ENZIMA (Nivel Superior):
       - Identifica variantes.
       - SECUENCIAS: Busca en Material Suplementario. Si dice "Mutante X", reconstruye la secuencia si es posible con certeza.

    2. ACTIVIDAD (Nivel Inferior):
       - Busca valores `mM product / mg enzyme`.
       - Separa claramente por tiempo (2h, 24h, etc.).
       - Si el sustrato es PET, especifica si es polvo, film, etc.

    3. EXPRESIÓN Y Tm:
       - Datos intrínsecos de la variante. Prioriza DSF para Tm.

    ¡SÉ UN AUDITOR EXTRICTO!
    """

    # 4. Ejecutar
    print("Iniciando extracción forense con Gemini...")
    response = model.generate_content([file_ref, system_prompt])
    
    return response.parsed

def flatten_data_to_csv(extraction_result: PaperExtraction) -> pd.DataFrame:
    rows = []
    
    if not extraction_result.variants:
        return pd.DataFrame()

    # Iteramos por cada enzima encontrada en el paper
    for variant in extraction_result.variants:
        
        # Datos comunes para todas las filas de esta enzima
        common_data = {
            "sample_id": variant.sample_id,
            "seq_aa": variant.seq_aa,      # Se extrae una vez, se usa muchas veces
            "seq_nuc": variant.seq_nuc,    # Se extrae una vez, se usa muchas veces
            "expression_mg_ml": variant.expression_mg_ml,
            "tm_c": variant.tm_c
        }
        
        # Iteramos por cada medición individual (2h, 24h, pH 7, pH 8...)
        for measurement in variant.measurements:
            # Creamos una fila combinando datos comunes + datos específicos
            row = common_data.copy()
            
            # Extract Evidence details
            evidence_data = {
                "snippet": measurement.evidence.raw_text_snippet,
                "page": measurement.evidence.page_number,
                "confidence": measurement.evidence.confidence_score
            }

            row.update({
                "time_h": measurement.time_h,
                "temperature_c": measurement.temperature_c,
                "pH": measurement.ph,
                "substrate": measurement.substrate,
                "mM_product": measurement.mM_product,
                "mM_product_per_mg_enzyme": measurement.mM_product_per_mg_enzyme,
                "well": measurement.well_id,
                **evidence_data # Flatten evidence into the row
            })
            rows.append(row)
            
    # Crear DataFrame
    df = pd.DataFrame(rows)
    
    # Reordenar columnas sugeridas
    column_order = [
        "sample_id", "time_h", "substrate", "temperature_c", "pH", 
        "well", "mM_product", "mM_product_per_mg_enzyme", 
        "seq_aa", "seq_nuc", "expression_mg_ml", "tm_c", 
        "confidence", "page", "snippet" 
    ]
    
    # Aseguramos que existan las columnas
    for col in column_order:
        if col not in df.columns:
            df[col] = None
            
    return df[column_order]
