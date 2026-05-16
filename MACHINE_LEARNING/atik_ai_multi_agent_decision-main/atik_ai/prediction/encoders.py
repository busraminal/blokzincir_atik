"""
ATIK AI - Bi-Encoder Architecture
Activity Encoder (E_A) ve Waste Encoder (E_W)

Formül:
v_A = E_A(NACE_description)
v_W = E_W(Waste_name, CPC_code)
"""
import logging
from typing import Optional, List, Union
from dataclasses import dataclass
import numpy as np

import torch
import torch.nn as nn

from ..core.exceptions import PredictionError

logger = logging.getLogger(__name__)


@dataclass
class EncoderConfig:
    """Encoder konfigürasyonu"""
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384
    hidden_dim: int = 256
    dropout: float = 0.1
    freeze_base: bool = False


class BaseEncoder(nn.Module):
    """
    Temel encoder sınıfı
    
    Transformer tabanlı metin encoder
    """
    
    def __init__(self, config: EncoderConfig = None):
        super().__init__()
        self.config = config or EncoderConfig()
        self._transformer = None
        self._tokenizer = None
        
        # Projection layer
        self.projection = nn.Sequential(
            nn.Linear(self.config.embedding_dim, self.config.hidden_dim),
            nn.ReLU(),
            nn.Dropout(self.config.dropout),
            nn.Linear(self.config.hidden_dim, self.config.hidden_dim)
        )
    
    def _load_transformer(self):
        """Lazy transformer yükleme"""
        if self._transformer is None:
            try:
                from transformers import AutoModel, AutoTokenizer
                
                self._tokenizer = AutoTokenizer.from_pretrained(self.config.model_name)
                self._transformer = AutoModel.from_pretrained(self.config.model_name)
                
                if self.config.freeze_base:
                    for param in self._transformer.parameters():
                        param.requires_grad = False
                
                logger.info(f"Transformer yüklendi: {self.config.model_name}")
            except Exception as e:
                raise PredictionError(f"Transformer yükleme hatası: {e}")
    
    def encode_text(self, text: Union[str, List[str]]) -> torch.Tensor:
        """Metni encode et"""
        self._load_transformer()
        
        if isinstance(text, str):
            text = [text]
        
        # Tokenize
        inputs = self._tokenizer(
            text,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt"
        )
        
        # Transformer çıktısı
        with torch.no_grad():
            outputs = self._transformer(**inputs)
        
        # Mean pooling
        attention_mask = inputs["attention_mask"]
        token_embeddings = outputs.last_hidden_state
        
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
        sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
        
        return sum_embeddings / sum_mask
    
    def forward(self, text: Union[str, List[str]]) -> torch.Tensor:
        """Forward pass"""
        base_embedding = self.encode_text(text)
        return self.projection(base_embedding)


class ActivityEncoder(BaseEncoder):
    """
    Activity Encoder (E_A)
    
    NACE/ISIC faaliyet açıklamasını vektörel ifadeye (v_A) çevirir.
    
    Input: NACE description
    Output: v_A ∈ R^256
    """
    
    def __init__(self, config: EncoderConfig = None):
        super().__init__(config)
        self.description_prefix = "Economic activity: "
    
    def encode(self, nace_description: Union[str, List[str]]) -> torch.Tensor:
        """
        NACE açıklamasını encode et
        
        Args:
            nace_description: NACE faaliyet açıklaması
            
        Returns:
            v_A: Activity embedding
        """
        if isinstance(nace_description, str):
            nace_description = [nace_description]
        
        # Prefix ekle
        texts = [f"{self.description_prefix}{desc}" for desc in nace_description]
        
        return self.forward(texts)
    
    def encode_nace_code(self, nace_code: str, code_descriptions: dict) -> torch.Tensor:
        """NACE kodunu encode et (açıklama lookup ile)"""
        description = code_descriptions.get(nace_code, nace_code)
        return self.encode(description)


class WasteEncoder(BaseEncoder):
    """
    Waste Encoder (E_W)
    
    Atık adını ve CPC kod açıklamasını vektörel ifadeye (v_W) çevirir.
    
    Input: Waste name + CPC code description
    Output: v_W ∈ R^256
    """
    
    def __init__(self, config: EncoderConfig = None):
        super().__init__(config)
        self.waste_prefix = "Waste material: "
    
    def encode(
        self,
        waste_name: Union[str, List[str]],
        cpc_description: Union[str, List[str]] = None
    ) -> torch.Tensor:
        """
        Atık bilgisini encode et
        
        Args:
            waste_name: Atık adı
            cpc_description: CPC kod açıklaması (opsiyonel)
            
        Returns:
            v_W: Waste embedding
        """
        if isinstance(waste_name, str):
            waste_name = [waste_name]
            if cpc_description and isinstance(cpc_description, str):
                cpc_description = [cpc_description]
        
        # Metin oluştur
        if cpc_description:
            texts = [
                f"{self.waste_prefix}{name}. Category: {cpc}"
                for name, cpc in zip(waste_name, cpc_description)
            ]
        else:
            texts = [f"{self.waste_prefix}{name}" for name in waste_name]
        
        return self.forward(texts)
    
    def encode_ewc_code(self, ewc_code: str, code_descriptions: dict) -> torch.Tensor:
        """EWC kodunu encode et"""
        description = code_descriptions.get(ewc_code, ewc_code)
        return self.encode(description)


class BiEncoder(nn.Module):
    """
    Bi-Encoder mimarisi
    
    Activity ve Waste encoder'ları birlikte
    
    v_concat = [v_A; v_W]
    y = σ(MLP(v_concat))
    """
    
    def __init__(self, config: EncoderConfig = None):
        super().__init__()
        self.config = config or EncoderConfig()
        
        self.activity_encoder = ActivityEncoder(config)
        self.waste_encoder = WasteEncoder(config)
        
        # Birleştirme ve sınıflandırma için MLP
        concat_dim = self.config.hidden_dim * 2
        self.classifier = nn.Sequential(
            nn.Linear(concat_dim, self.config.hidden_dim),
            nn.ReLU(),
            nn.Dropout(self.config.dropout),
            nn.Linear(self.config.hidden_dim, 64),
            nn.ReLU(),
            nn.Dropout(self.config.dropout),
            nn.Linear(64, 1),
            nn.Sigmoid()
        )
    
    def forward(
        self,
        activity_desc: Union[str, List[str]],
        waste_name: Union[str, List[str]],
        cpc_description: Union[str, List[str]] = None
    ) -> torch.Tensor:
        """
        Forward pass
        
        Returns:
            Prediction score [0, 1]
        """
        # Encode
        v_a = self.activity_encoder.encode(activity_desc)
        v_w = self.waste_encoder.encode(waste_name, cpc_description)
        
        # Birleştir: [v_A; v_W]
        v_concat = torch.cat([v_a, v_w], dim=-1)
        
        # Sınıflandır
        return self.classifier(v_concat)
    
    def predict(
        self,
        activity_desc: str,
        waste_name: str,
        threshold: float = 0.5
    ) -> tuple:
        """
        Tahmin yap
        
        Returns:
            (label, confidence)
        """
        self.eval()
        with torch.no_grad():
            score = self.forward(activity_desc, waste_name).item()
        
        label = score > threshold
        return label, score


# Kolay kullanım için factory fonksiyonlar
def create_activity_encoder(pretrained: str = None) -> ActivityEncoder:
    """Activity encoder oluştur"""
    config = EncoderConfig()
    encoder = ActivityEncoder(config)
    
    if pretrained:
        encoder.load_state_dict(torch.load(pretrained))
    
    return encoder


def create_waste_encoder(pretrained: str = None) -> WasteEncoder:
    """Waste encoder oluştur"""
    config = EncoderConfig()
    encoder = WasteEncoder(config)
    
    if pretrained:
        encoder.load_state_dict(torch.load(pretrained))
    
    return encoder


def create_bi_encoder(pretrained: str = None) -> BiEncoder:
    """Bi-encoder oluştur"""
    config = EncoderConfig()
    model = BiEncoder(config)
    
    if pretrained:
        model.load_state_dict(torch.load(pretrained))
    
    return model
