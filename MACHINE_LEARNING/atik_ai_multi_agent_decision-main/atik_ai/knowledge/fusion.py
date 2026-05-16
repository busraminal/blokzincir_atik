"""
ATIK AI - Entity Fusion
Sentence-BERT ile varlık birleştirme

Farklı isimlerle anılan aynı maddeleri birleştirir:
"Bio-ash" ve "Fly ash" → tek düğüm (cosine > 0.8)
"""
import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import numpy as np

from ..core.exceptions import KnowledgeGraphError

logger = logging.getLogger(__name__)


@dataclass
class Entity:
    """Varlık (entity)"""
    id: str
    name: str
    entity_type: str  # waste, process, resource
    embedding: Optional[np.ndarray] = None
    aliases: List[str] = None
    
    def __post_init__(self):
        if self.aliases is None:
            self.aliases = []


@dataclass
class FusionResult:
    """Birleştirme sonucu"""
    canonical_name: str
    merged_entities: List[str]
    similarity_scores: List[float]


class EntityFusion:
    """
    Varlık Birleştirme (Entity Fusion)
    
    Sentence-BERT kullanarak benzer varlıkları birleştirir.
    Kosinüs benzerliği > 0.8 → aynı varlık
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", similarity_threshold: float = 0.8):
        self.model_name = model_name
        self.similarity_threshold = similarity_threshold
        self._model = None
        self._entity_cache: Dict[str, np.ndarray] = {}
    
    @property
    def model(self):
        """Lazy Sentence-BERT model yükleme"""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
                logger.info(f"Sentence-BERT model yüklendi: {self.model_name}")
            except ImportError:
                raise KnowledgeGraphError("sentence-transformers paketi yüklü değil")
        return self._model
    
    def get_embedding(self, text: str) -> np.ndarray:
        """Metin için embedding al (cache'li)"""
        if text not in self._entity_cache:
            embedding = self.model.encode(text, convert_to_numpy=True)
            self._entity_cache[text] = embedding
        return self._entity_cache[text]
    
    def compute_similarity(self, text1: str, text2: str) -> float:
        """
        İki metin arasındaki kosinüs benzerliği
        
        Returns:
            Similarity score [0, 1]
        """
        emb1 = self.get_embedding(text1)
        emb2 = self.get_embedding(text2)
        
        # Kosinüs benzerliği
        similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
        
        return float(similarity)
    
    def are_same_entity(self, name1: str, name2: str) -> Tuple[bool, float]:
        """
        İki isim aynı varlığı mı temsil ediyor?
        
        Returns:
            (is_same, similarity_score)
        """
        similarity = self.compute_similarity(name1, name2)
        is_same = similarity >= self.similarity_threshold
        
        return is_same, similarity
    
    def find_duplicates(self, entities: List[str]) -> List[FusionResult]:
        """
        Listedeki duplicate varlıkları bul
        
        Returns:
            List of FusionResult (birleştirilecek gruplar)
        """
        n = len(entities)
        if n < 2:
            return []
        
        # Tüm embedding'leri hesapla
        embeddings = [self.get_embedding(e) for e in entities]
        
        # Benzerlik matrisi
        similarity_matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(i + 1, n):
                sim = np.dot(embeddings[i], embeddings[j]) / (
                    np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[j])
                )
                similarity_matrix[i, j] = sim
                similarity_matrix[j, i] = sim
        
        # Birleştirilecek grupları bul (Union-Find benzeri)
        merged = [False] * n
        results = []
        
        for i in range(n):
            if merged[i]:
                continue
            
            group = [entities[i]]
            scores = []
            
            for j in range(i + 1, n):
                if not merged[j] and similarity_matrix[i, j] >= self.similarity_threshold:
                    group.append(entities[j])
                    scores.append(similarity_matrix[i, j])
                    merged[j] = True
            
            if len(group) > 1:
                # En kısa ismi canonical olarak seç
                canonical = min(group, key=len)
                results.append(FusionResult(
                    canonical_name=canonical,
                    merged_entities=group,
                    similarity_scores=scores
                ))
                merged[i] = True
        
        return results
    
    def merge_entities(self, entities: List[str]) -> Dict[str, str]:
        """
        Varlıkları birleştir ve mapping döndür
        
        Returns:
            {original_name: canonical_name}
        """
        mapping = {e: e for e in entities}  # Varsayılan: kendisi
        
        duplicates = self.find_duplicates(entities)
        
        for result in duplicates:
            for entity in result.merged_entities:
                mapping[entity] = result.canonical_name
        
        logger.info(f"{len(duplicates)} duplicate grup bulundu, {len(entities)} varlık birleştirildi")
        
        return mapping
    
    def get_canonical_name(self, name: str, known_entities: List[str]) -> Tuple[str, float]:
        """
        Bilinen varlıklar arasında en benzerini bul
        
        Returns:
            (canonical_name, similarity_score)
        """
        if not known_entities:
            return name, 1.0
        
        best_match = name
        best_score = 0.0
        
        for entity in known_entities:
            sim = self.compute_similarity(name, entity)
            if sim > best_score:
                best_score = sim
                best_match = entity
        
        if best_score >= self.similarity_threshold:
            return best_match, best_score
        else:
            return name, 1.0  # Yeni varlık
    
    def cluster_entities(self, entities: List[str], n_clusters: int = None) -> Dict[int, List[str]]:
        """
        Varlıkları kümelere ayır
        
        Returns:
            {cluster_id: [entity_names]}
        """
        from sklearn.cluster import AgglomerativeClustering
        
        if len(entities) < 2:
            return {0: entities}
        
        # Embedding'ler
        embeddings = np.array([self.get_embedding(e) for e in entities])
        
        # Kümeleme
        if n_clusters is None:
            n_clusters = max(1, len(entities) // 5)
        
        clustering = AgglomerativeClustering(
            n_clusters=min(n_clusters, len(entities)),
            metric='cosine',
            linkage='average'
        )
        labels = clustering.fit_predict(embeddings)
        
        # Sonuçları grupla
        clusters = {}
        for i, label in enumerate(labels):
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(entities[i])
        
        return clusters
    
    def standardize_name(self, name: str) -> str:
        """İsmi standartlaştır (lowercase, trim, vb.)"""
        import re
        
        # Lowercase
        name = name.lower().strip()
        
        # Çoklu boşlukları tek boşluğa indir
        name = re.sub(r'\s+', ' ', name)
        
        # Parantez içindekileri temizle
        name = re.sub(r'\([^)]*\)', '', name).strip()
        
        return name
    
    def batch_standardize(self, names: List[str]) -> List[str]:
        """Toplu standardizasyon"""
        return [self.standardize_name(n) for n in names]
    
    def clear_cache(self):
        """Embedding cache'ini temizle"""
        self._entity_cache.clear()
        logger.debug("Entity cache temizlendi")
