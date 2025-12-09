# src/models.py

from pydantic import BaseModel, Field
from typing import List, Optional, Literal

# --- Nivel 0: Evidencia ---
class Evidence(BaseModel):
    raw_text_snippet: str = Field(..., description="Texto exacto o fila de tabla. COPIAR LITERAL.")
    page_number: int = Field(..., description="Página del PDF.")
    location_type: str = Field(..., description="Ej: 'Table 1', 'Figure 3', 'Results Text'.")
    confidence_score: float = Field(..., description="Certeza (0.0 - 1.0).")

# --- Nivel 0.5: Parámetro Cinético Genérico ---
# Esto soluciona el requisito de "manejar todas las formas de reporte" (kcat, KM, etc.)
class KineticParameter(BaseModel):
    type: Literal['kcat', 'Km', 'Vmax', 'SpecificActivity', 'ProductConcentration', 'Conversion', 'HalfLife', 'Other'] = Field(..., description="Tipo de parámetro cinético reportado.")
    value: float = Field(..., description="Valor numérico.")
    unit: str = Field(..., description="Unidad reportada (ej: 'min-1', 'mM', 'U/mg', '%').")
    standard_deviation: Optional[float] = Field(None, description="Desviación estándar si se reporta.")

# --- Nivel 1: El Experimento ---
class ActivityExperiment(BaseModel):
    # Condiciones Experimentales
    time_h: Optional[float] = Field(None, description="Duración del ensayo en horas.")
    temperature_c: float = Field(..., description="Temperatura en Celsius.")
    ph: float = Field(..., description="pH del buffer.")
    
    # Metadatos del Sustrato (Crítico según el email)
    substrate_name: str = Field(..., description="Nombre del sustrato (ej. 'PET').")
    substrate_morphology: Optional[str] = Field(None, description="Forma física: 'film', 'powder', 'nanoparticles', 'coupon'. Importante por la cristalinidad.")
    substrate_crystallinity_pct: Optional[float] = Field(None, description="Porcentaje de cristalinidad si se menciona.")

    # Lista flexible de resultados
    reported_metrics: List[KineticParameter] = Field(..., description="Lista de todos los valores cinéticos reportados para este experimento.")
    
    evidence: Evidence

# --- Nivel 2: La Enzima ---
class EnzymeVariant(BaseModel):
    sample_id: str = Field(..., description="Nombre/ID de la variante (ej. 'LCC_ICCG').")
    
    # Secuencias
    seq_aa: str = Field(..., description="Secuencia de aminoácidos.")
    seq_nuc: Optional[str] = Field(None, description="Secuencia de nucleótidos.")
    
    # Expresión y Estabilidad (Tm)
    expression_mg_ml: Optional[float] = Field(None, description="Expresión soluble en mg/mL.")
    tm_c: Optional[float] = Field(None, description="Temperatura de fusión (Tm) medida idealmente por DSF.")
    
    measurements: List[ActivityExperiment]

# --- Nivel 3: Resultado Final ---
class ExtractionResult(BaseModel):
    paper_doi: Optional[str] = Field(None, description="DOI del paper.")
    variants: List[EnzymeVariant]

# Alias for compatibility
PaperExtraction = ExtractionResult
