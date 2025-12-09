import typing_extensions as typing
from pydantic import BaseModel, Field
from typing import List, Optional

# --- Nivel 0: Evidencia Forense ---
class Evidence(BaseModel):
    raw_text_snippet: str = Field(..., description="El texto exacto o fila de la tabla de donde se extrajo el dato. COPIAR Y PEGAR LITERAL.")
    page_number: int = Field(..., description="Número de página del PDF donde se encuentra esta evidencia.")
    location_type: str = Field(..., description="Tipo de fuente visual: 'Table', 'Figure', 'TextParagraph', 'SupplementaryTable'")
    confidence_score: float = Field(..., description="Nivel de confianza (0.0 a 1.0) de que este dato es correcto.")

# --- Nivel 1: La Medición Individual (Lo que será una fila) ---
class ActivityExperiment(BaseModel):
    time_h: float = Field(..., description="Tiempo de reacción: 2, 24, 48, etc.")
    temperature_c: float = Field(..., description="Temperatura del ensayo en Celsius")
    ph: float = Field(..., description="pH del buffer utilizado")
    substrate: str = Field(..., description="Nombre exacto del sustrato (ej. 'PET powder', 'aFilm')")
    
    # El valor crítico
    mM_product: float = Field(..., description="Concentración de producto en mM")
    mM_product_per_mg_enzyme: float = Field(..., description="Actividad normalizada (mM prod / mg enzima)")
    
    # Metadatos de la medición
    well_id: Optional[str] = Field(None, description="Si se menciona el pocillo (ej. 'A1', 'H12')")
    replicate_id: Optional[int] = Field(None, description="Número de réplica si aplica")
    
    # Evidencia Forense (Obligatoria)
    evidence: Evidence = Field(..., description="La prueba forense de dónde salió este dato específico.")

# --- Nivel 2: La Enzima (El contenedor) ---
class EnzymeVariant(BaseModel):
    sample_id: str = Field(..., description="ID de la muestra o nombre de la variante (ej. 'LCC_ICCG')")
    
    # SECUENCIAS (Obligatorias según tu indicación)
    seq_aa: str = Field(..., description="Secuencia completa de AMINOÁCIDOS")
    seq_nuc: Optional[str] = Field(None, description="Secuencia de NUCLEÓTIDOS (ADN) codificante")
    
    # Datos de expresión y estabilidad (se repiten para la misma enzima)
    expression_mg_ml: Optional[float] = Field(None, description="Concentración de expresión (mg/mL)")
    tm_c: Optional[float] = Field(None, description="Temperatura de fusión (Tm)")
    
    # Lista de experimentos (Aquí está la magia para luego aplanar)
    measurements: List[ActivityExperiment] = Field(..., description="Lista de todas las mediciones hechas con esta enzima")

# --- Nivel 3: El Resultado del Paper ---
class PaperExtraction(BaseModel):
    paper_doi: Optional[str] = Field(None, description="DOI del paper")
    variants: List[EnzymeVariant]

# Backward compatibility alias or just reuse PaperExtraction as the main result
ExtractionResult = PaperExtraction
