"""
ATIK AI - API Schemas
Pydantic modeller
"""
from typing import List, Dict, Optional, Tuple, Any
from pydantic import BaseModel, Field
from datetime import datetime, date
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class MatchQuality(str, Enum):
    """Eşleşme kalitesi"""
    EXCELLENT = "excellent"
    GOOD = "good"
    MODERATE = "moderate"
    WEAK = "weak"


# =============================================================================
# BASE MODELS
# =============================================================================

class Coordinates(BaseModel):
    """Koordinatlar"""
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


# =============================================================================
# FACILITY MODELS
# =============================================================================

class FacilityBase(BaseModel):
    """Tesis temel"""
    name: str
    nace_code: str
    address: Optional[str] = None
    city: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None


class FacilityCreate(FacilityBase):
    """Tesis oluşturma"""
    sector_id: Optional[int] = None
    ewc_codes: List[str] = []


class FacilityResponse(FacilityBase):
    """Tesis yanıt"""
    id: int
    sector_id: Optional[int] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class FacilityDetail(FacilityResponse):
    """Tesis detay"""
    ewc_codes: List[str] = []
    waste_profiles: List[Dict] = []
    match_count: int = 0


# =============================================================================
# MATCHING MODELS
# =============================================================================

class MatchScore(BaseModel):
    """Eşleşme skoru"""
    overall: float = Field(..., ge=0, le=1)
    technical: float = Field(..., ge=0, le=1)
    temporal: float = Field(..., ge=0, le=1)
    distance: float = Field(..., ge=0, le=1)


class MatchResult(BaseModel):
    """Eşleşme sonucu"""
    source_id: int
    receiver_id: int
    ewc_code: str
    score: MatchScore
    distance_km: float
    quality: MatchQuality
    is_economically_feasible: Optional[bool] = None
    rank: int = 0


# =============================================================================
# FEASIBILITY MODELS
# =============================================================================

class FeasibilityRequest(BaseModel):
    """Fizibilite isteği - SWAN Model"""
    source_facility_id: int = Field(..., description="Kaynak tesis ID")
    receiver_facility_id: int = Field(..., description="Alıcı tesis ID")
    waste_type_id: int = Field(0, description="Atık tipi ID")
    ewc_code: str = Field(..., description="EWC atık kodu (örn: 70213)")
    waste_quantity_ton: float = Field(..., gt=0, description="Atık miktarı (ton)")
    distance_km: float = Field(..., gt=0, description="Mesafe (km)")
    # Opsiyonel
    source_storage_cost: Optional[float] = Field(None, description="Kaynak depolama maliyeti (₺/ton/gün)")
    receiver_storage_cost: Optional[float] = Field(None, description="Alıcı depolama maliyeti (₺/ton/gün)")
    initial_price: Optional[float] = Field(None, description="Başlangıç pazarlık fiyatı (₺/ton)")


class TransportCost(BaseModel):
    """Nakliye maliyeti"""
    distance_km: float
    num_trucks: int
    total_cost: float
    cost_per_ton: float
    fuel_cost: float


class BreakEvenAnalysis(BaseModel):
    """Break-even analizi"""
    source_break_even: float
    receiver_break_even: float
    suggested_price: float
    negotiation_margin: float
    is_feasible: bool


class FeasibilityResult(BaseModel):
    """Fizibilite sonucu"""
    source_facility_id: int
    receiver_facility_id: int
    waste_quantity_ton: float
    transport: TransportCost
    source_profit: float
    receiver_profit: float
    break_even: BreakEvenAnalysis
    is_feasible: bool
    decision_reason: str
    recommendations: List[str] = []


class FeasibilityResponse(BaseModel):
    """Fizibilite yanıtı"""
    request_id: str
    result: FeasibilityResult
    report: Optional[str] = None


# =============================================================================
# DISTANCE MODELS
# =============================================================================

class DistanceRequest(BaseModel):
    """Mesafe isteği"""
    origin: Coordinates
    destination: Coordinates


class DistanceResponse(BaseModel):
    """Mesafe yanıtı"""
    distance_km: float
    duration_min: Optional[float] = None
    source: str  # osmnx, ors, haversine


# =============================================================================
# HEALTH & STATUS
# =============================================================================

class HealthCheck(BaseModel):
    """Sağlık kontrolü"""
    status: str
    version: str
    database: str
    cache: str
    timestamp: datetime
