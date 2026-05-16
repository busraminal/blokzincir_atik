"""
ATIK AI - FastAPI Routes
API endpoint'leri
"""
import logging
from typing import List, Optional
from datetime import datetime
import uuid

from fastapi import APIRouter, FastAPI, HTTPException, Query

from .schemas import (
    FacilityCreate, FacilityResponse, FacilityDetail,
    MatchResult as ApiMatchResult,
    MatchScore,
    MatchQuality,
    FeasibilityRequest, FeasibilityResponse, FeasibilityResult,
    TransportCost, BreakEvenAnalysis,
    DistanceRequest, DistanceResponse,
    HealthCheck,
)
from ..core.database import DatabaseManager
from .insights_routes import llm_router, predict_router

logger = logging.getLogger(__name__)


def _overall_to_quality(overall: float) -> MatchQuality:
    if overall >= 0.8:
        return MatchQuality.EXCELLENT
    if overall >= 0.6:
        return MatchQuality.GOOD
    if overall >= 0.4:
        return MatchQuality.MODERATE
    return MatchQuality.WEAK

# =============================================================================
# DATABASE
# =============================================================================

db_manager = DatabaseManager()

# =============================================================================
# ROUTERS
# =============================================================================

# Ana router
api_router = APIRouter(prefix="/api/v1")

# Alt router'lar
facilities_router = APIRouter(prefix="/facilities", tags=["Facilities"])
matching_router = APIRouter(prefix="/matching", tags=["Matching"])
feasibility_router = APIRouter(prefix="/feasibility", tags=["Feasibility"])
distance_router = APIRouter(prefix="/distance", tags=["Distance"])
health_router = APIRouter(prefix="/health", tags=["Health"])


# =============================================================================
# FACILITIES
# =============================================================================

@facilities_router.get("/", response_model=List[FacilityResponse])
async def list_facilities(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    city: Optional[str] = None,
    nace_code: Optional[str] = None
):
    """Tesisleri listele"""
    offset = (page - 1) * per_page
    
    sql = """
        SELECT id, facility_name, nace_code, city, latitude, longitude, sector_id
        FROM facilities
        WHERE 1=1
    """
    params = {}
    
    if city:
        sql += " AND city ILIKE :city"
        params["city"] = f"%{city}%"
    if nace_code:
        sql += " AND nace_code LIKE :nace_code"
        params["nace_code"] = f"{nace_code}%"
    
    sql += f" OFFSET {offset} LIMIT {per_page}"
    
    try:
        rows = db_manager.execute_sql(sql, params)
        return [
            FacilityResponse(
                id=row[0],
                name=row[1] or "",
                nace_code=row[2] or "",
                city=row[3],
                lat=float(row[4]) if row[4] else None,
                lon=float(row[5]) if row[5] else None,
                sector_id=row[6],
                created_at=datetime.now()
            )
            for row in rows
        ]
    except Exception as e:
        logger.error(f"List facilities error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@facilities_router.get("/{facility_id}", response_model=FacilityDetail)
async def get_facility(facility_id: int):
    """Tesis detayı"""
    sql = """
        SELECT id, facility_name, nace_code, city, latitude, longitude, 
               sector_id, facility_type, storage_capacity_ton
        FROM facilities
        WHERE id = :id
    """
    try:
        rows = db_manager.execute_sql(sql, {"id": facility_id})
        if not rows:
            raise HTTPException(status_code=404, detail="Tesis bulunamadı")
        
        row = rows[0]
        return FacilityDetail(
            id=row[0],
            name=row[1] or "",
            nace_code=row[2] or "",
            city=row[3],
            lat=float(row[4]) if row[4] else None,
            lon=float(row[5]) if row[5] else None,
            sector_id=row[6],
            created_at=datetime.now(),
            ewc_codes=[],
            match_count=0
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get facility error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@facilities_router.get("/{facility_id}/matches", response_model=List[ApiMatchResult])
async def get_facility_matches(
    facility_id: int,
    limit: int = Query(10, ge=1, le=50)
):
    """Tesis eşleşmelerini getir (match_candidates tablosu)"""
    sql = """
        SELECT receiver_facility_id, waste_code, overall_score, technical_score,
               temporal_score, distance_score, distance_km, rank_order
        FROM match_candidates
        WHERE source_facility_id = :sid
        ORDER BY rank_order ASC, overall_score DESC
        LIMIT :lim
    """
    try:
        rows = db_manager.execute_sql(sql, {"sid": facility_id, "lim": limit})
    except Exception as e:
        logger.warning("match_candidates okunamadı: %s", e)
        return []
    out: List[ApiMatchResult] = []
    for row in rows:
        rid, wcode, ov, te, tm, di, dkm, rk = row
        ov = float(ov or 0)
        te = float(te or 0)
        tm = float(tm or 0)
        di = float(di or 0)
        out.append(
            ApiMatchResult(
                source_id=facility_id,
                receiver_id=int(rid),
                ewc_code=str(wcode or ""),
                score=MatchScore(overall=ov, technical=te, temporal=tm, distance=di),
                distance_km=float(dkm or 0),
                quality=_overall_to_quality(ov),
                is_economically_feasible=None,
                rank=int(rk or len(out) + 1),
            )
        )
    return out


@facilities_router.post("/")
async def create_facility(facility: FacilityCreate):
    """Yeni tesis oluştur"""
    sql = """
        INSERT INTO facilities (facility_name, nace_code, city, latitude, longitude, sector_id)
        VALUES (:name, :nace_code, :city, :lat, :lon, :sector_id)
        RETURNING id
    """
    try:
        result = db_manager.execute_sql(sql, {
            "name": facility.name,
            "nace_code": facility.nace_code,
            "city": facility.city,
            "lat": facility.lat,
            "lon": facility.lon,
            "sector_id": facility.sector_id
        })
        new_id = result[0][0] if result else None
        
        return {
            "id": new_id,
            "name": facility.name,
            "message": "Tesis oluşturuldu"
        }
    except Exception as e:
        logger.error(f"Create facility error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# MATCHING
# =============================================================================

def _ewc_lookup_sql_params(waste_code: str):
    """EWC hem '150106' hem '15 01 06' biçiminde gelebilir."""
    raw = (waste_code or "").strip()
    compact = "".join(c for c in raw if c.isdigit())
    return raw, compact


@matching_router.post("/search")
async def search_matches(
    waste_code: str,
    max_distance_km: int = Query(50, ge=1, le=500),
    limit: int = Query(20, ge=1, le=100),
    min_quality_score: int = Query(0, ge=0, le=100),
    source_facility_id: Optional[int] = Query(
        None,
        description="Kaynak tesis (facilities.id). Verilirse MatchingEngine ile skorlu eşleşme.",
    ),
):
    """
    Atık koduna göre eşleştirmeleri ara
    
    Parametreler:
    - waste_code: EWC atık kodu (örn: 150106)
    - max_distance_km: Max mesafe (default: 50 km)
    - limit: Max sonuç (default: 20)
    - min_quality_score: Min kalite skoru (0-100), genel skor eşiği olarak kullanılır
    - source_facility_id: Opsiyonel; veritabanındaki kaynak tesis — `atik_ai.matching.MatchingEngine` devreye girer
    """
    try:
        raw_code, compact = _ewc_lookup_sql_params(waste_code)
        if not compact and not raw_code:
            raise HTTPException(status_code=400, detail="waste_code gerekli")

        sql = """
            SELECT waste_code, description FROM waste_types
            WHERE waste_code = :raw
               OR REPLACE(waste_code, ' ', '') = :compact
            LIMIT 1
        """
        rows = db_manager.execute_sql(
            sql, {"raw": raw_code or compact, "compact": compact or raw_code}
        )

        if not rows:
            return {"matches": [], "message": f"Atık kodu '{waste_code}' bulunamadı"}

        db_waste_code = rows[0][0] or raw_code or compact
        description = rows[0][1] if rows else None

        # Çok katmanlı eşleştirme (teknik + zamansal + mesafe), PostgreSQL tesis verisi gerekir
        if source_facility_id is not None:
            from ..matching.engine import MatchingEngine

            src_sql = """
                SELECT id, facility_name, nace_code, latitude, longitude
                FROM facilities WHERE id = :id LIMIT 1
            """
            src_rows = db_manager.execute_sql(src_sql, {"id": source_facility_id})
            if not src_rows:
                raise HTTPException(
                    status_code=404,
                    detail=f"Tesis bulunamadı: source_facility_id={source_facility_id}",
                )
            s = src_rows[0]
            lat, lon = s[3], s[4]
            if lat is None or lon is None:
                return {
                    "waste_code": db_waste_code,
                    "description": description,
                    "max_distance_km": max_distance_km,
                    "matches": [],
                    "message": "Kaynak tesisin latitude/longitude değerleri yok; eşleştirme yapılamıyor.",
                    "matching_engine": True,
                }

            rec_sql = """
                SELECT id, facility_name, nace_code, latitude, longitude
                FROM facilities
                WHERE id != :sid
                  AND latitude IS NOT NULL
                  AND longitude IS NOT NULL
                LIMIT 500
            """
            rec_rows = db_manager.execute_sql(rec_sql, {"sid": source_facility_id})
            receivers = []
            names = {}
            for r in rec_rows:
                rid, rname, rnace, rlat, rlon = r[0], r[1], r[2], r[3], r[4]
                receivers.append(
                    {
                        "id": rid,
                        "nace": (rnace or "").strip(),
                        "coords": (float(rlat), float(rlon)),
                    }
                )
                names[rid] = rname or ""

            source = {
                "id": int(s[0]),
                "nace": (s[2] or "").strip(),
                "ewc_codes": [str(db_waste_code).strip()],
                "coords": (float(lat), float(lon)),
            }

            min_overall = max(0.0, min(1.0, min_quality_score / 100.0))
            engine = MatchingEngine(
                max_distance_km=float(max_distance_km),
                min_overall_score=min_overall,
            )
            ranked = engine.find_matches(
                source=source,
                receivers=receivers,
                max_results=limit,
            )
            matches_out = []
            for m in ranked:
                d = m.to_dict()
                d["receiver_name"] = names.get(m.receiver_id, "")
                matches_out.append(d)

            msg = (
                f"{len(matches_out)} aday (MatchingEngine: teknik+zamansal+mesafe)."
                if matches_out
                else "Motor çalıştı; NACE–EWC / mesafe eşiği nedeniyle aday yok. "
                "Başka bir kaynak tesis veya daha geniş mesafe deneyin."
            )
            return {
                "waste_code": db_waste_code,
                "description": description,
                "max_distance_km": max_distance_km,
                "source_facility_id": source_facility_id,
                "matches": matches_out,
                "message": msg,
                "matching_engine": True,
            }

        return {
            "waste_code": db_waste_code,
            "description": description,
            "max_distance_km": max_distance_km,
            "matches": [],
            "message": "Skorlu liste için source_facility_id (kaynak tesis id) gönderin; "
            "aksi halde yalnızca kod doğrulaması yapılır.",
            "matching_engine": False,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search matches error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@matching_router.get("/ewc-codes")
async def list_ewc_codes():
    """Desteklenen EWC/atık kodlarını listele"""
    try:
        sql = "SELECT waste_code, description, status FROM waste_types ORDER BY waste_code"
        rows = db_manager.execute_sql(sql)
        return [
            {
                "code": r[0],
                "description": r[1],
                "status": r[2]
            }
            for r in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@matching_router.get("/waste-types")
async def list_waste_types(ewc_code: Optional[str] = None):
    """Atık tiplerini listele"""
    try:
        sql = "SELECT waste_code, description, status, sector_id FROM waste_types"
        params = {}
        
        if ewc_code:
            sql += " WHERE waste_code LIKE :code"
            params["code"] = f"{ewc_code}%"
        
        sql += " ORDER BY waste_code LIMIT 100"
        
        rows = db_manager.execute_sql(sql, params)
        return [
            {
                "waste_code": r[0],
                "description": r[1],
                "status": r[2],
                "sector_id": r[3]
            }
            for r in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FEASIBILITY
# =============================================================================

@feasibility_router.post("/analyze")
async def analyze_feasibility(request: FeasibilityRequest):
    """
    SWAN Model Ekonomik Fizibilite Analizi
    
    Girdiler:
    - source_facility_id: Kaynak tesis ID
    - receiver_facility_id: Alıcı tesis ID  
    - waste_type_id: Atık tipi ID
    - ewc_code: EWC atık kodu (örn: "70213")
    - waste_quantity_ton: Atık miktarı (ton)
    - distance_km: Mesafe (km)
    
    Çıktı: Fizibilite analizi (kar, maliyet, karar)
    """
    try:
        from ..economics.feasibility import SwanFeasibilityAnalyzer
        
        analyzer = SwanFeasibilityAnalyzer()
        
        result = analyzer.analyze(
            source_facility_id=request.source_facility_id,
            receiver_facility_id=request.receiver_facility_id,
            ewc_code=request.ewc_code,
            waste_quantity_ton=request.waste_quantity_ton,
            distance_km=request.distance_km,
            waste_type_id=request.waste_type_id
        )
        
        return {
            "request_id": str(uuid.uuid4()),
            "result": result.to_dict(),
            "summary": {
                "is_feasible": result.is_feasible,
                "decision": result.decision_reason,
                "suggested_price": result.break_even.suggested_price,
                "source_profit_per_ton": result.source_profit.profit_per_ton,
                "receiver_profit_per_ton": result.receiver_profit.profit_per_ton,
                "confidence": result.confidence_score
            }
        }
        
    except Exception as e:
        logger.error(f"Feasibility error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@feasibility_router.post("/quick-check")
async def quick_feasibility_check(
    source_lat: float,
    source_lon: float,
    receiver_lat: float,
    receiver_lon: float,
    waste_quantity: float,
    disposal_savings: float = 50,
    commercial_price: float = 100
):
    """Hızlı fizibilite kontrolü"""
    try:
        from ..economics import FeasibilityAnalyzer
        
        analyzer = FeasibilityAnalyzer()
        
        is_feasible, reason = analyzer.quick_feasibility_check(
            source_coords=(source_lat, source_lon),
            receiver_coords=(receiver_lat, receiver_lon),
            waste_quantity=waste_quantity,
            disposal_savings=disposal_savings,
            commercial_price=commercial_price
        )
        
        return {
            "is_feasible": is_feasible,
            "reason": reason
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# DISTANCE
# =============================================================================

@distance_router.post("/calculate", response_model=DistanceResponse)
async def calculate_distance(request: DistanceRequest):
    """İki nokta arası mesafe"""
    try:
        from ..distance import DistanceCalculator
        
        calculator = DistanceCalculator()
        
        result = calculator.calculate(
            origin=(request.origin.lat, request.origin.lon),
            destination=(request.destination.lat, request.destination.lon)
        )
        
        return DistanceResponse(
            distance_km=result.distance_km,
            duration_min=result.duration_min,
            source=result.source
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# HEALTH
# =============================================================================

@health_router.get("/", response_model=HealthCheck)
async def health_check():
    """Sistem sağlık kontrolü"""
    db_status = "disconnected"
    
    try:
        # Veritabanı bağlantısını kontrol et
        from sqlalchemy import text
        with db_manager.session() as session:
            session.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        db_status = f"error: {str(e)[:50]}"
    
    return HealthCheck(
        status="healthy" if db_status == "connected" else "degraded",
        version="1.0.0",
        database=db_status,
        cache="not_configured",
        timestamp=datetime.now()
    )


@health_router.get("/stats")
async def get_stats():
    """Sistem istatistikleri"""
    try:
        facility_count = db_manager.execute_sql("SELECT COUNT(*) FROM facilities")[0][0]
        waste_type_count = db_manager.execute_sql("SELECT COUNT(*) FROM waste_types")[0][0]
        
        try:
            match_count = db_manager.execute_sql("SELECT COUNT(*) FROM match_candidates")[0][0]
        except Exception:
            match_count = 0
        return {
            "facilities": facility_count,
            "waste_types": waste_type_count,
            "matches": match_count,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# REGISTER ROUTERS
# =============================================================================

api_router.include_router(facilities_router)
api_router.include_router(matching_router)
api_router.include_router(feasibility_router)
api_router.include_router(distance_router)
api_router.include_router(health_router)
api_router.include_router(predict_router)
api_router.include_router(llm_router)

# =============================================================================
# CREATE FASTAPI APP
# =============================================================================

app = FastAPI(
    title="ATIK AI",
    description="Circular Economy Waste-to-Material Matching System",
    version="1.0.0"
)

# Include main router
app.include_router(api_router)
