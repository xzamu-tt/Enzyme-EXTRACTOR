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
    # Condiciones Experimentales
    time_h: Optional[float] = Field(default=None, description="Duración del ensayo en horas.")
    temperature_c: Optional[float] = Field(default=None, description="Temperatura en Celsius.")
    ph: Optional[float] = Field(default=None, description="pH del buffer.")
    
    # NUEVOS METADATOS PARA NORMALIZACIÓN
    reaction_volume_ml: Optional[float] = Field(default=None, description="Volumen de reacción en mL.")
    
    # Carga de enzima (valor + unidad)
    enzyme_loading_value: Optional[float] = Field(default=None, description="Cantidad de enzima cargada.")
    enzyme_loading_unit: Optional[str] = Field(default=None, description="Unidad: 'mg/mL', 'nM', 'µM', 'mg enzyme/g PET', etc.")
    
    # Metadatos del Sustrato
    substrate_name: Optional[str] = Field(default=None, description="Nombre del sustrato (ej. 'PET').")
    substrate_morphology: Optional[str] = Field(default=None, description="Forma física: 'film', 'powder', etc.")
    substrate_crystallinity_pct: Optional[float] = Field(default=None, description="Porcentaje de cristalinidad.")
    
    # Cantidad de sustrato (valor + unidad)
    substrate_amount_value: Optional[float] = Field(default=None, description="Cantidad inicial de sustrato.")
    substrate_amount_unit: Optional[str] = Field(default=None, description="Unidad: 'mg', 'g', 'mg/mL', etc.")

    # PRODUCTO/YIELD CRUDO - TAL CUAL SE REPORTA
    product_yield_raw: Optional[str] = Field(default=None, description="El dato de producto/yield EXACTAMENTE como aparece en el artículo (ej: '15.2 µg/mg PET', '45% conversion', '2.3 mM TPA').")
    product_yield_unit: Optional[str] = Field(default=None, description="La unidad del yield si se puede separar.")

    # Lista flexible de otros resultados cinéticos
    reported_metrics: List[KineticParameter] = Field(description="Lista de valores cinéticos reportados (kcat, Km, etc.).")
    
    evidence: Evidence = Field(description="Evidencia forense del dato.")

# --- Nivel 2: La Enzima ---
class EnzymeVariant(BaseModel):
    sample_id: str = Field(description="Nombre/ID de la variante (ej. 'LCC-ICCG').")
    
    # Secuencias
    seq_aa: Optional[str] = Field(default=None, description="Secuencia de aminoácidos.")
    seq_nuc: Optional[str] = Field(default=None, description="Secuencia de nucleótidos.")
    
    # Expresión
    expression_value: Optional[float] = Field(default=None, description="Valor numérico de expresión.")
    expression_unit: Optional[str] = Field(default=None, description="Unidad: 'mg/mL', 'mg/L', 'g/L', etc.")
    
    # Estabilidad térmica
    tm_c: Optional[float] = Field(default=None, description="Temperatura de fusión (Tm) en Celsius.")
    
    measurements: List[ActivityExperiment] = Field(description="Lista de mediciones de actividad.")

# --- Nivel 3: Resultado Final ---
class ExtractionResult(BaseModel):
    paper_doi: Optional[str] = Field(default=None, description="DOI del paper.")
    variants: List[EnzymeVariant] = Field(description="Lista de variantes enzimáticas encontradas.")

# Alias
PaperExtraction = ExtractionResult
