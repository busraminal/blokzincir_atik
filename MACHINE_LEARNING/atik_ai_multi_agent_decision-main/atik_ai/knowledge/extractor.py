"""
ATIK AI - Triple Extractor
LLM ile metinden W-P-R üçlüleri çıkarma

Makalelerden:
[Atık (W) - Süreç (P) - Kaynak (R)]
"""
import logging
import json
import re
from typing import List, Optional
from dataclasses import dataclass

from .graph import Triple
from ..core.exceptions import KnowledgeGraphError

logger = logging.getLogger(__name__)


EXTRACTION_PROMPT = """You are an expert in industrial symbiosis and waste valorization.
Extract Waste-Process-Resource triples from the following text.

For each transformation described, identify:
- Waste: The input waste material
- Process: The transformation process(es) applied
- Resource: The output product or material

Return the results as a JSON array of objects with keys: waste, process, resource

Text:
{text}

JSON Output:"""


@dataclass
class ExtractionResult:
    """Triple çıkarma sonucu"""
    triples: List[Triple]
    raw_text: str
    source_doi: Optional[str] = None
    extraction_method: str = "llm"
    confidence: float = 0.9


class TripleExtractor:
    """
    LLM tabanlı Triple Çıkarıcı
    
    Metinden Waste-Process-Resource üçlülerini çıkarır.
    """
    
    def __init__(self, model: str = "gpt-4o", api_key: str = None):
        self.model = model
        self._client = None
        self._api_key = api_key
    
    @property
    def client(self):
        """Lazy OpenAI client"""
        if self._client is None:
            try:
                from openai import OpenAI
                import os
                api_key = self._api_key or os.getenv("OPENAI_API_KEY")
                self._client = OpenAI(api_key=api_key)
            except ImportError:
                raise KnowledgeGraphError("openai paketi yüklü değil")
        return self._client
    
    def extract_from_text(self, text: str, doi: str = None) -> ExtractionResult:
        """
        Metinden tripleları çıkar
        
        Args:
            text: Analiz edilecek metin
            doi: Kaynak DOI
            
        Returns:
            ExtractionResult
        """
        if not text or len(text.strip()) < 50:
            return ExtractionResult(triples=[], raw_text=text, source_doi=doi)
        
        prompt = EXTRACTION_PROMPT.format(text=text[:4000])  # Token limiti
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a waste valorization expert. Extract information precisely."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            triples = self._parse_response(content, doi)
            
            logger.info(f"Metinden {len(triples)} triple çıkarıldı")
            
            return ExtractionResult(
                triples=triples,
                raw_text=text,
                source_doi=doi,
                extraction_method="llm",
                confidence=0.9
            )
            
        except Exception as e:
            logger.error(f"LLM extraction hatası: {e}")
            return ExtractionResult(triples=[], raw_text=text, source_doi=doi)
    
    def _parse_response(self, response: str, doi: str = None) -> List[Triple]:
        """LLM yanıtını parse et"""
        triples = []
        
        # JSON bloğunu bul
        json_match = re.search(r'\[[\s\S]*\]', response)
        if not json_match:
            return triples
        
        try:
            data = json.loads(json_match.group())
            
            for item in data:
                if isinstance(item, dict):
                    waste = item.get("waste", "").strip()
                    process = item.get("process", "").strip()
                    resource = item.get("resource", "").strip()
                    
                    if waste and process and resource:
                        triples.append(Triple(
                            waste=waste,
                            process=process,
                            resource=resource,
                            doi=doi,
                            confidence=0.9
                        ))
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse hatası: {e}")
        
        return triples
    
    def extract_from_abstract(self, abstract: str, doi: str = None) -> ExtractionResult:
        """Makale özetinden çıkar"""
        return self.extract_from_text(abstract, doi)
    
    def extract_from_paper(self, full_text: str, doi: str = None, chunk_size: int = 3000) -> ExtractionResult:
        """
        Tam makale metninden çıkar
        
        Büyük metinleri parçalara böler
        """
        all_triples = []
        
        # Metni parçalara böl
        chunks = [full_text[i:i+chunk_size] for i in range(0, len(full_text), chunk_size)]
        
        for i, chunk in enumerate(chunks):
            logger.debug(f"Chunk {i+1}/{len(chunks)} işleniyor")
            result = self.extract_from_text(chunk, doi)
            all_triples.extend(result.triples)
        
        # Duplicate'leri temizle
        unique_triples = self._deduplicate_triples(all_triples)
        
        return ExtractionResult(
            triples=unique_triples,
            raw_text=full_text[:1000] + "...",
            source_doi=doi,
            extraction_method="llm_chunked",
            confidence=0.85
        )
    
    def _deduplicate_triples(self, triples: List[Triple]) -> List[Triple]:
        """Duplicate tripleları temizle"""
        seen = set()
        unique = []
        
        for t in triples:
            key = (t.waste.lower(), t.process.lower(), t.resource.lower())
            if key not in seen:
                seen.add(key)
                unique.append(t)
        
        return unique


class RuleBasedExtractor:
    """
    Kural tabanlı triple çıkarıcı
    
    LLM olmadan basit pattern matching
    """
    
    PROCESS_KEYWORDS = [
        "pyrolysis", "gasification", "fermentation", "composting",
        "anaerobic digestion", "hydrolysis", "combustion", "extraction",
        "distillation", "separation", "conversion", "treatment"
    ]
    
    RESOURCE_KEYWORDS = [
        "biogas", "biochar", "syngas", "biofuel", "ethanol", "methane",
        "compost", "fertilizer", "energy", "fuel", "oil", "char",
        "hydrogen", "electricity", "heat"
    ]
    
    def extract(self, text: str, doi: str = None) -> List[Triple]:
        """Basit kural tabanlı çıkarma"""
        triples = []
        text_lower = text.lower()
        
        # Her cümleyi analiz et
        sentences = re.split(r'[.!?]', text)
        
        for sentence in sentences:
            sentence_lower = sentence.lower()
            
            # Süreç kelimesi var mı?
            for process in self.PROCESS_KEYWORDS:
                if process in sentence_lower:
                    # Kaynak kelimesi var mı?
                    for resource in self.RESOURCE_KEYWORDS:
                        if resource in sentence_lower:
                            # Basit atık tespiti (of/from pattern)
                            waste_match = re.search(
                                rf"([\w\s]+)\s+(?:of|from|using)\s+",
                                sentence_lower
                            )
                            if waste_match:
                                waste = waste_match.group(1).strip()
                                if len(waste) > 3:
                                    triples.append(Triple(
                                        waste=waste,
                                        process=process,
                                        resource=resource,
                                        doi=doi,
                                        confidence=0.6
                                    ))
        
        return triples
