# src/models.py

from pydantic import BaseModel, Field
from typing import List, Optional

# --- Nivel 0: Evidencia ---
class Evidence(BaseModel):
    raw_text_snippet: str = Field(description="Texto exacto o fila de tabla. COPIAR LITERAL.")
    page_number: int = Field(description="Página del PDF. 0 si es Excel/imagen.")
    location_type: str = Field(description="Ej: 'Table 1', 'Figure 3', 'Excel Sheet 1'.")
    confidence_score: float = Field(description="Certeza (0.0 - 1.0).")

# --- Nivel 0.5: Parámetro Cinético Genérico ---
class KineticParameter(BaseModel):
    type: str = Field(description="Tipo: 'kcat', 'Km', 'Vmax', 'SpecificActivity', 'ProductConcentration', 'Conversion', 'HalfLife', 'Other'.")
    value: float = Field(description="Valor numérico.")
    unit: str = Field(description="Unidad reportada (ej: 'min-1', 'mM', 'U/mg', '%').")
    standard_deviation: Optional[float] = Field(default=None, description="Desviación estándar si se reporta.")

# --- Nivel 1: El Experimento ---
class ActivityExperiment(BaseModel):
    # Condiciones Experimentales - AHORA OPCIONALES (muchos papers no las reportan)
    time_h: Optional[float] = Field(default=None, description="Duración del ensayo en horas.")
    temperature_c: Optional[float] = Field(default=None, description="Temperatura en Celsius.")
    ph: Optional[float] = Field(default=None, description="pH del buffer.")
    
    # Metadatos del Sustrato
    substrate_name: Optional[str] = Field(default=None, description="Nombre del sustrato (ej. 'PET').")
    substrate_morphology: Optional[str] = Field(default=None, description="Forma física: 'film', 'powder', etc.")
    substrate_crystallinity_pct: Optional[float] = Field(default=None, description="Porcentaje de cristalinidad.")

    # Lista flexible de resultados
    reported_metrics: List[KineticParameter] = Field(description="Lista de valores cinéticos reportados.")
    
    evidence: Evidence = Field(description="Evidencia forense del dato.")

# --- Nivel 2: La Enzima ---
class EnzymeVariant(BaseModel):
    sample_id: str = Field(description="Nombre/ID de la variante (ej. 'LCC-ICCG').")
    
    # Secuencias - OPCIONALES (no todos los papers las tienen)
    seq_aa: Optional[str] = Field(default=None, description="Secuencia de aminoácidos.")
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
