"""
ATIK AI - SQLAlchemy Modelleri
Tüm veritabanı tabloları
"""
from datetime import datetime
from typing import Optional, List
from decimal import Decimal

from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, 
    DateTime, ForeignKey, Numeric, UniqueConstraint, Index
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


# =============================================================================
# TEMEL TABLOLAR
# =============================================================================

class Sector(Base):
    """Sektörler tablosu"""
    __tablename__ = "sectors"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sector_name = Column(String(255), unique=True, nullable=False)
    nace_code = Column(String(10))
    description = Column(Text)
    created_at = Column(DateTime, default=func.now())
    
    # İlişkiler
    facilities = relationship("Facility", back_populates="sector")
    waste_types = relationship("WasteType", back_populates="sector")
    
    def __repr__(self):
        return f"<Sector(id={self.id}, name='{self.sector_name}')>"


class EWCCode(Base):
    """EWC-Stat Atık Kodları"""
    __tablename__ = "ewc_codes"
    
    code = Column(String(10), primary_key=True)
    description = Column(Text, nullable=False)
    category = Column(String(100))
    hazardous = Column(Boolean, default=False)
    
    # İlişkiler
    waste_types = relationship("WasteType", back_populates="ewc")


class NACECode(Base):
    """NACE Ekonomik Faaliyet Kodları"""
    __tablename__ = "nace_codes"
    
    code = Column(String(10), primary_key=True)
    description = Column(Text, nullable=False)
    level = Column(Integer)
    parent_code = Column(String(10))
    
    def __repr__(self):
        return f"<NACECode(code='{self.code}')>"


class Facility(Base):
    """Tesisler tablosu"""
    __tablename__ = "facilities"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    sector_id = Column(Integer, ForeignKey("sectors.id"))
    nace_code = Column(String(10))
    
    # Konum
    latitude = Column(Numeric(10, 6))
    longitude = Column(Numeric(10, 6))
    address = Column(Text)
    city = Column(String(100))
    
    # Operasyon bilgisi (zamansal uyum için)
    operation_start_month = Column(Integer)  # 1-12
    operation_end_month = Column(Integer)    # 1-12
    
    # İletişim
    contact_email = Column(String(255))
    contact_phone = Column(String(50))
    
    # Zaman damgaları
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # İlişkiler
    sector = relationship("Sector", back_populates="facilities")
    waste_profiles = relationship("FacilityWasteProfile", back_populates="facility")
    source_matches = relationship("MatchCandidate", foreign_keys="MatchCandidate.source_facility_id", back_populates="source_facility")
    receiver_matches = relationship("MatchCandidate", foreign_keys="MatchCandidate.receiver_facility_id", back_populates="receiver_facility")
    
    # İndeksler
    __table_args__ = (
        Index('idx_facilities_location', 'latitude', 'longitude'),
        Index('idx_facilities_nace', 'nace_code'),
    )
    
    @property
    def coords(self):
        """Koordinat tuple'ı"""
        if self.latitude and self.longitude:
            return (float(self.latitude), float(self.longitude))
        return None
    
    def __repr__(self):
        return f"<Facility(id={self.id}, name='{self.name}')>"


# =============================================================================
# ATIK TABLOLARI
# =============================================================================

class WasteType(Base):
    """Atık Türleri"""
    __tablename__ = "waste_types"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    waste_code = Column(String(20), unique=True, nullable=False)
    ewc_code = Column(String(10), ForeignKey("ewc_codes.code"))
    description = Column(Text)
    status = Column(String(50))
    sector_id = Column(Integer, ForeignKey("sectors.id"))
    
    # Fiziksel özellikler
    unit = Column(String(20), default="ton")
    density_kg_m3 = Column(Numeric(10, 2))
    
    created_at = Column(DateTime, default=func.now())
    
    # İlişkiler
    sector = relationship("Sector", back_populates="waste_types")
    ewc = relationship("EWCCode", back_populates="waste_types")
    history = relationship("WasteHistory", back_populates="waste_type")
    profiles = relationship("FacilityWasteProfile", back_populates="waste_type")
    matches = relationship("MatchCandidate", back_populates="waste_type")
    
    __table_args__ = (
        Index('idx_waste_types_ewc', 'ewc_code'),
    )
    
    def __repr__(self):
        return f"<WasteType(code='{self.waste_code}')>"


class WasteHistory(Base):
    """Atık Geçmişi (Yıllık veriler)"""
    __tablename__ = "waste_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    waste_code = Column(String(20), ForeignKey("waste_types.waste_code"))
    year = Column(Integer, nullable=False)
    disposal_amount_ton = Column(Numeric(15, 2))
    total_waste_ton = Column(Numeric(15, 2))
    
    # İlişkiler
    waste_type = relationship("WasteType", back_populates="history")
    
    __table_args__ = (
        UniqueConstraint('waste_code', 'year', name='uq_waste_history_code_year'),
    )


class FacilityWasteProfile(Base):
    """Tesis Atık Profili (Bi-Encoder tahminleri)"""
    __tablename__ = "facility_waste_profiles"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    facility_id = Column(Integer, ForeignKey("facilities.id"), nullable=False)
    waste_type_id = Column(Integer, ForeignKey("waste_types.id"), nullable=False)
    
    # Tahmin sonuçları (Bi-Encoder)
    produces = Column(Boolean)              # PR model sonucu
    produces_confidence = Column(Numeric(5, 4))
    needs = Column(Boolean)                 # NR model sonucu
    needs_confidence = Column(Numeric(5, 4))
    
    # Gerçek veriler (varsa)
    verified = Column(Boolean, default=False)
    annual_quantity_ton = Column(Numeric(15, 2))
    
    # Zamansal bilgi
    availability_start_month = Column(Integer)
    availability_end_month = Column(Integer)
    
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # İlişkiler
    facility = relationship("Facility", back_populates="waste_profiles")
    waste_type = relationship("WasteType", back_populates="profiles")
    
    __table_args__ = (
        UniqueConstraint('facility_id', 'waste_type_id', name='uq_facility_waste_profile'),
        Index('idx_facility_waste_profile_facility', 'facility_id'),
    )


# =============================================================================
# EŞLEŞME TABLOLARI
# =============================================================================

class MatchCandidate(Base):
    """Eşleşme Adayları"""
    __tablename__ = "match_candidates"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Taraflar
    source_facility_id = Column(Integer, ForeignKey("facilities.id"), nullable=False)
    receiver_facility_id = Column(Integer, ForeignKey("facilities.id"), nullable=False)
    waste_type_id = Column(Integer, ForeignKey("waste_types.id"), nullable=False)
    
    # Mesafe
    distance_km = Column(Numeric(10, 2))
    distance_source = Column(String(50))  # osmnx, ors, google, haversine
    
    # Teknik uyum skoru
    technical_score = Column(Numeric(5, 4))
    
    # Zamansal uyum
    temporal_compatible = Column(Boolean, default=True)
    storage_days_required = Column(Integer, default=0)
    
    # Durum: pending, analyzing, feasible, not_feasible, approved, rejected
    status = Column(String(50), default="pending")
    
    created_at = Column(DateTime, default=func.now())
    
    # İlişkiler
    source_facility = relationship("Facility", foreign_keys=[source_facility_id], back_populates="source_matches")
    receiver_facility = relationship("Facility", foreign_keys=[receiver_facility_id], back_populates="receiver_matches")
    waste_type = relationship("WasteType", back_populates="matches")
    economic_analysis = relationship("EconomicAnalysis", back_populates="match", uselist=False)
    
    __table_args__ = (
        Index('idx_match_candidates_status', 'status'),
    )
    
    def __repr__(self):
        return f"<MatchCandidate(id={self.id}, status='{self.status}')>"


class EconomicAnalysis(Base):
    """Ekonomik Analiz Sonuçları (SWAN)"""
    __tablename__ = "economic_analysis"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("match_candidates.id"), unique=True, nullable=False)
    
    # Atık miktarı
    waste_quantity_ton = Column(Numeric(15, 2))
    
    # Lojistik
    num_trucks = Column(Integer)
    transport_cost = Column(Numeric(15, 2))
    
    # Kaynak tesis kârı (S_profit)
    waste_sale_price = Column(Numeric(15, 2))      # P_W
    disposal_savings = Column(Numeric(15, 2))       # CMM_W
    source_profit = Column(Numeric(15, 2))          # S_profit
    
    # Alıcı tesis kârı (R_profit)
    commercial_price = Column(Numeric(15, 2))       # P_COM
    storage_cost = Column(Numeric(15, 2))           # ST_W
    receiver_profit = Column(Numeric(15, 2))        # R_profit
    
    # Break-even analizi
    break_even_source = Column(Numeric(15, 2))      # P_WBES
    break_even_receiver = Column(Numeric(15, 2))    # P_WBER
    suggested_price = Column(Numeric(15, 2))        # Önerilen fiyat
    
    # Karar
    is_feasible = Column(Boolean)
    decision_reason = Column(Text)
    
    calculated_at = Column(DateTime, default=func.now())
    
    # İlişkiler
    match = relationship("MatchCandidate", back_populates="economic_analysis")
    
    def __repr__(self):
        return f"<EconomicAnalysis(match_id={self.match_id}, feasible={self.is_feasible})>"


# =============================================================================
# BİLGİ GRAFİĞİ KAYNAKLARI
# =============================================================================

class AcademicSource(Base):
    """Akademik Referanslar"""
    __tablename__ = "academic_sources"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    doi = Column(String(255), unique=True)
    title = Column(Text)
    authors = Column(Text)
    journal = Column(String(255))
    year = Column(Integer)
    abstract = Column(Text)
    processed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    
    # İlişkiler
    wpr_relations = relationship("WasteProcessResource", back_populates="source")


class WasteProcessResource(Base):
    """W-P-R İlişkileri (Ana veri seti)"""
    __tablename__ = "waste_process_resource"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    waste = Column(String(255), nullable=False)
    process = Column(Text, nullable=False)
    resource = Column(String(255), nullable=False)
    doi_reference = Column(String(255), ForeignKey("academic_sources.doi"))
    confidence_score = Column(Numeric(5, 4))
    created_at = Column(DateTime, default=func.now())
    
    # İlişkiler
    source = relationship("AcademicSource", back_populates="wpr_relations")
    
    def __repr__(self):
        return f"<WPR(waste='{self.waste[:20]}...', resource='{self.resource[:20]}...')>"


# =============================================================================
# NACE-EWC EŞLEŞME KURALLARI
# =============================================================================

class NACEEWCMapping(Base):
    """NACE-EWC Eşleşme Kuralları (Teknik eşleştirme için)"""
    __tablename__ = "nace_ewc_mappings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    nace_code = Column(String(10), nullable=False)
    ewc_code = Column(String(10), nullable=False)
    relationship_type = Column(String(50))  # produces, needs
    confidence = Column(Numeric(5, 4), default=1.0)
    source = Column(String(100))  # regulation, literature, manual
    
    __table_args__ = (
        UniqueConstraint('nace_code', 'ewc_code', 'relationship_type', name='uq_nace_ewc_mapping'),
    )


# =============================================================================
# YARDIMCI FONKSİYONLAR
# =============================================================================

def create_all_tables(engine):
    """Tüm tabloları oluştur"""
    Base.metadata.create_all(engine)


def drop_all_tables(engine):
    """Tüm tabloları sil"""
    Base.metadata.drop_all(engine)
