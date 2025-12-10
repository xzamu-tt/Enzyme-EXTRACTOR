# src/models.py

from pydantic import BaseModel, Field
from typing import List, Optional

# --- Nivel 0: Evidencia ---
class Evidence(BaseModel):
    raw_text_snippet: str = Field(description="Texto exacto o fila de tabla. COPIAR LITERAL.")
    page_number: int = Field(description="Página del PDF.")
    location_type: str = Field(description="Ej: 'Table 1', 'Figure 3', 'Results Text'.")
    confidence_score: float = Field(description="Certeza (0.0 - 1.0).")

# --- Nivel 0.5: Parámetro Cinético Genérico ---
class KineticParameter(BaseModel):
    # Cambiado de Literal a str para compatibilidad con Gemini response_schema
    type: str = Field(description="Tipo: 'kcat', 'Km', 'Vmax', 'SpecificActivity', 'ProductConcentration', 'Conversion', 'HalfLife', 'Other'.")
    value: float = Field(description="Valor numérico.")
    unit: str = Field(description="Unidad reportada (ej: 'min-1', 'mM', 'U/mg', '%').")
    standard_deviation: Optional[float] = Field(default=None, description="Desviación estándar si se reporta.")

# --- Nivel 1: El Experimento ---
class ActivityExperiment(BaseModel):
    # Condiciones Experimentales
    time_h: Optional[float] = Field(default=None, description="Duración del ensayo en horas.")
    temperature_c: float = Field(description="Temperatura en Celsius.")
    ph: float = Field(description="pH del buffer.")
    
    # Metadatos del Sustrato
    substrate_name: str = Field(description="Nombre del sustrato (ej. 'PET').")
    substrate_morphology: Optional[str] = Field(default=None, description="Forma física: 'film', 'powder', 'nanoparticles', 'coupon'.")
    substrate_crystallinity_pct: Optional[float] = Field(default=None, description="Porcentaje de cristalinidad si se menciona.")

    # Lista flexible de resultados
    reported_metrics: List[KineticParameter] = Field(description="Lista de todos los valores cinéticos reportados.")
    
    evidence: Evidence = Field(description="Evidencia forense del dato.")

# --- Nivel 2: La Enzima ---
class EnzymeVariant(BaseModel):
    sample_id: str = Field(description="Nombre/ID de la variante (ej. 'LCC_ICCG').")
    
    # Secuencias
    seq_aa: str = Field(description="Secuencia de aminoácidos.")
    seq_nuc: Optional[str] = Field(default=None, description="Secuencia de nucleótidos.")
    
    # Expresión y Estabilidad
    expression_mg_ml: Optional[float] = Field(default=None, description="Expresión soluble en mg/mL.")
    tm_c: Optional[float] = Field(default=None, description="Temperatura de fusión (Tm).")
    
    measurements: List[ActivityExperiment] = Field(description="Lista de mediciones de actividad.")

# --- Nivel 3: Resultado Final ---
class ExtractionResult(BaseModel):
    paper_doi: Optional[str] = Field(default=None, description="DOI del paper.")
    variants: List[EnzymeVariant] = Field(description="Lista de variantes enzimáticas encontradas.")

# Alias
PaperExtraction = ExtractionResult
