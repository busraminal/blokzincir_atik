"""
ATIK AI - Waste Predictor
PR (Produce) ve NR (Need) modelleri

PR Model: y > 0.5 → Produce = True
NR Model: y > 0.5 → Need = True
"""
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np

import torch

from .encoders import BiEncoder, EncoderConfig
from ..core.exceptions import PredictionError

logger = logging.getLogger(__name__)


@dataclass
class PredictionResult:
    """Tahmin sonucu"""
    label: bool
    confidence: float
    model_type: str  # "produce" or "need"
    
    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "confidence": self.confidence,
            "model_type": self.model_type
        }


@dataclass
class WasteProfile:
    """Bir atık için tesis profili"""
    waste_name: str
    waste_code: str
    produces: Optional[PredictionResult] = None
    needs: Optional[PredictionResult] = None
    
    @property
    def is_producer(self) -> bool:
        return self.produces and self.produces.label
    
    @property
    def is_consumer(self) -> bool:
        return self.needs and self.needs.label


@dataclass
class FacilityProfile:
    """Tesis waste profili"""
    facility_id: int
    facility_name: str
    nace_code: str
    nace_description: str
    waste_profiles: List[WasteProfile] = field(default_factory=list)
    
    @property
    def produced_wastes(self) -> List[str]:
        """Tesisin ürettiği atıklar"""
        return [wp.waste_name for wp in self.waste_profiles if wp.is_producer]
    
    @property
    def needed_resources(self) -> List[str]:
        """Tesisin ihtiyaç duyduğu kaynaklar"""
        return [wp.waste_name for wp in self.waste_profiles if wp.is_consumer]
    
    def to_dict(self) -> dict:
        return {
            "facility_id": self.facility_id,
            "facility_name": self.facility_name,
            "nace_code": self.nace_code,
            "produced_wastes": self.produced_wastes,
            "needed_resources": self.needed_resources,
            "total_profiles": len(self.waste_profiles)
        }


class WastePredictor:
    """
    Atık Tahminleyici
    
    Şirketlerin beyan etmediği potansiyeli tahmin eder.
    - PR Model: Şirket bu atığı üretir mi?
    - NR Model: Şirket bu kaynağa ihtiyaç duyar mı?
    """
    
    def __init__(
        self,
        produce_model: BiEncoder = None,
        need_model: BiEncoder = None,
        threshold: float = 0.5,
        device: str = None
    ):
        self.threshold = threshold
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        
        # Modeller
        self._produce_model = produce_model
        self._need_model = need_model
        
        # Lazy loading için
        self._models_loaded = False
    
    def _load_models(self):
        """Modelleri yükle (lazy)"""
        if self._models_loaded:
            return
        
        config = EncoderConfig()
        
        if self._produce_model is None:
            self._produce_model = BiEncoder(config)
            logger.info("PR model oluşturuldu (untrained)")
        
        if self._need_model is None:
            self._need_model = BiEncoder(config)
            logger.info("NR model oluşturuldu (untrained)")
        
        self._produce_model.to(self.device)
        self._need_model.to(self.device)
        
        self._models_loaded = True
    
    def load_pretrained(self, produce_path: str, need_path: str):
        """Önceden eğitilmiş modelleri yükle"""
        self._load_models()
        
        self._produce_model.load_state_dict(torch.load(produce_path, map_location=self.device))
        self._need_model.load_state_dict(torch.load(need_path, map_location=self.device))
        
        self._produce_model.eval()
        self._need_model.eval()
        
        logger.info("Pretrained modeller yüklendi")
    
    def predict_produces(
        self,
        nace_description: str,
        waste_name: str,
        cpc_description: str = None
    ) -> PredictionResult:
        """
        PR Model: Tesis bu atığı üretir mi?
        
        y = σ(MLP([v_A; v_W]))
        y > 0.5 → Produce = True
        """
        self._load_models()
        self._produce_model.eval()
        
        with torch.no_grad():
            score = self._produce_model.forward(
                nace_description,
                waste_name,
                cpc_description
            ).item()
        
        return PredictionResult(
            label=score > self.threshold,
            confidence=score,
            model_type="produce"
        )
    
    def predict_needs(
        self,
        nace_description: str,
        resource_name: str,
        cpc_description: str = None
    ) -> PredictionResult:
        """
        NR Model: Tesis bu kaynağa ihtiyaç duyar mı?
        
        y = σ(MLP([v_A; v_W]))
        y > 0.5 → Need = True
        """
        self._load_models()
        self._need_model.eval()
        
        with torch.no_grad():
            score = self._need_model.forward(
                nace_description,
                resource_name,
                cpc_description
            ).item()
        
        return PredictionResult(
            label=score > self.threshold,
            confidence=score,
            model_type="need"
        )
    
    def profile_facility(
        self,
        facility_id: int,
        facility_name: str,
        nace_code: str,
        nace_description: str,
        waste_list: List[Dict]
    ) -> FacilityProfile:
        """
        Tesis için tam waste profili oluştur
        
        Args:
            facility_id: Tesis ID
            facility_name: Tesis adı
            nace_code: NACE kodu
            nace_description: NACE açıklaması
            waste_list: [{"name": "...", "code": "...", "cpc": "..."}]
            
        Returns:
            FacilityProfile
        """
        profile = FacilityProfile(
            facility_id=facility_id,
            facility_name=facility_name,
            nace_code=nace_code,
            nace_description=nace_description
        )
        
        for waste in waste_list:
            waste_name = waste.get("name", "")
            waste_code = waste.get("code", "")
            cpc_desc = waste.get("cpc", None)
            
            # Üretim tahmini
            produces = self.predict_produces(nace_description, waste_name, cpc_desc)
            
            # İhtiyaç tahmini
            needs = self.predict_needs(nace_description, waste_name, cpc_desc)
            
            profile.waste_profiles.append(WasteProfile(
                waste_name=waste_name,
                waste_code=waste_code,
                produces=produces,
                needs=needs
            ))
        
        logger.info(f"Profil oluşturuldu: {facility_name} - {len(profile.waste_profiles)} waste")
        return profile
    
    def batch_predict_produces(
        self,
        nace_descriptions: List[str],
        waste_names: List[str]
    ) -> List[PredictionResult]:
        """Toplu üretim tahmini"""
        self._load_models()
        self._produce_model.eval()
        
        results = []
        with torch.no_grad():
            # Batch halinde encode et
            scores = self._produce_model.forward(nace_descriptions, waste_names)
            
            for score in scores:
                results.append(PredictionResult(
                    label=score.item() > self.threshold,
                    confidence=score.item(),
                    model_type="produce"
                ))
        
        return results
    
    def find_potential_matches(
        self,
        producer_profile: FacilityProfile,
        consumer_profile: FacilityProfile,
        min_confidence: float = 0.6
    ) -> List[Tuple[str, float, float]]:
        """
        İki tesis arasındaki potansiyel eşleşmeleri bul
        
        Returns:
            [(waste_name, producer_confidence, consumer_confidence)]
        """
        matches = []
        
        producer_wastes = {
            wp.waste_name: wp.produces.confidence
            for wp in producer_profile.waste_profiles
            if wp.is_producer and wp.produces.confidence >= min_confidence
        }
        
        for wp in consumer_profile.waste_profiles:
            if wp.is_consumer and wp.needs.confidence >= min_confidence:
                if wp.waste_name in producer_wastes:
                    matches.append((
                        wp.waste_name,
                        producer_wastes[wp.waste_name],
                        wp.needs.confidence
                    ))
        
        # Confidence'a göre sırala
        matches.sort(key=lambda x: x[1] * x[2], reverse=True)
        
        return matches
    
    def save_models(self, produce_path: str, need_path: str):
        """Modelleri kaydet"""
        self._load_models()
        
        torch.save(self._produce_model.state_dict(), produce_path)
        torch.save(self._need_model.state_dict(), need_path)
        
        logger.info(f"Modeller kaydedildi: {produce_path}, {need_path}")
