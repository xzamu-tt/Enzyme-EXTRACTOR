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
        
        # 3. Configurar el modelo con el esquema Pydantic (Gemini 3 Pro)
        generation_config = {
            "temperature": 1.0,  # Gemini 3: Mantener en 1.0 para razonamiento óptimo
            "response_mime_type": "application/json",
            "response_schema": ExtractionResult,
            # Gemini 3: thinking_level para control de razonamiento
            "thinking_config": {"thinking_level": "high"}  # high = máxima profundidad de razonamiento
        }
        
        model = genai.GenerativeModel(
            model_name="gemini-3-pro-preview",  # Gemini 3 Pro (nuevo modelo)
            generation_config=generation_config
        )

        # 4. PROMPT "MODO EXHAUSTIVO" - Anti-Lazy AI
        system_prompt = """
        ROL: Auditor Forense de Datos Masivos (Data Scraper Mode).
        
        TU OBJETIVO PRINCIPAL:
        Extraer el 100% de los puntos de datos cinéticos encontrados en TODO el documento (Texto, Tablas principales, Tablas suplementarias, Figuras).
        
        RIESGO DE IA PEREZOSA (STRICT RULES):
        1. PROHIBIDO RESUMIR: Si una tabla tiene 50 filas con 50 variantes, debes generar 50 entradas en la lista 'variants'. No extraigas solo la "mejor" o la primera.
        2. REDUNDANCIA: La actividad catalítica se reporta a menudo varias veces (ej. en texto y luego en tabla). EXTRAE AMBAS instancias si tienen diferente contexto o si confirman el dato.
        3. MULTI-MÉTRICA: Una misma reacción suele tener kcat, KM y Actividad Específica. Extrae TODAS las métricas reportadas para ese experimento.
        4. BÚSQUEDA PROFUNDA: No te detengas en el Abstract. El 90% de los datos valiosos están en las Tablas de Resultados y Material Suplementario (páginas finales).
        
        INSTRUCCIONES DE EXTRACCIÓN:
        
        VARIANTES:
        - Busca: "Wild Type", "Mutant", códigos como "LCC-ICCG", nombres de enzimas.
        - Cada variante es una entrada separada en 'variants'.
        
        CONDICIONES EXPERIMENTALES:
        - pH variables, Temperaturas variables. Cada cambio de condición es un NUEVO experimento (measurement).
        - Tiempo de reacción (2h, 24h, 48h) - cada timepoint es un measurement distinto.
        
        MÉTRICAS CINÉTICAS:
        - Usa `reported_metrics` para capturar TODAS las métricas: kcat, Km, Vmax, SpecificActivity, ProductConcentration, Conversion, HalfLife, Other.
        - NO calcules ni conviertas unidades. Extrae TAL CUAL aparecen.
        
        SUSTRATOS:
        - Identifica morfología (polvo, film, pastilla) en `substrate_morphology`.
        - Cristalinidad (%) en `substrate_crystallinity_pct` si se menciona.
        
        EXPRESIÓN Y TM:
        - Expresión: mg/mL (fracción soluble).
        - Tm: Melting Temperature, preferiblemente por DSF.
        
        SECUENCIAS:
        - Busca en Material Suplementario. Si hay mutaciones descritas, intenta reconstruir.
        
        REGLA DE ORO DE EVIDENCIA:
        - TODO dato debe tener su 'raw_text_snippet' copiado LITERALMENTE del PDF.
        - Incluye número de página y tipo de fuente (Table 1, Figure 3, Supplementary Table S2).
        
        FORMATO DE SALIDA:
        JSON estricto cumpliendo el esquema proporcionado. SIN RESÚMENES, DATOS COMPLETOS.
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

