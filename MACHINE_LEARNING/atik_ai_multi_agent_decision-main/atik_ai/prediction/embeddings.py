"""
ATIK AI - Embedding Manager
Embedding hesaplama, depolama ve arama
"""
import logging
from typing import List, Dict, Optional, Tuple, Union
from pathlib import Path
import pickle
import numpy as np

from ..core.exceptions import PredictionError

logger = logging.getLogger(__name__)


class EmbeddingManager:
    """
    Embedding yöneticisi
    
    - Metin embedding hesaplama
    - FAISS ile hızlı benzerlik arama
    - Disk'e kaydetme/yükleme
    """
    
    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        cache_dir: str = "./cache/embeddings"
    ):
        self.model_name = model_name
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self._model = None
        self._index = None
        self._id_map: Dict[int, str] = {}  # FAISS idx -> entity_id
        self._embedding_cache: Dict[str, np.ndarray] = {}
    
    @property
    def model(self):
        """Lazy model loading"""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
                logger.info(f"Embedding model yüklendi: {self.model_name}")
            except ImportError:
                raise PredictionError("sentence-transformers paketi yüklü değil")
        return self._model
    
    # =========================================================================
    # EMBEDDING HESAPLAMA
    # =========================================================================
    
    def encode(self, text: Union[str, List[str]], normalize: bool = True) -> np.ndarray:
        """
        Metni embedding'e dönüştür
        
        Args:
            text: Metin veya metin listesi
            normalize: L2 normalize
            
        Returns:
            Embedding array
        """
        embeddings = self.model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=normalize,
            show_progress_bar=False
        )
        
        return embeddings
    
    def get_embedding(self, text: str, use_cache: bool = True) -> np.ndarray:
        """Tek metin için embedding (cache'li)"""
        if use_cache and text in self._embedding_cache:
            return self._embedding_cache[text]
        
        embedding = self.encode(text)
        
        if use_cache:
            self._embedding_cache[text] = embedding
        
        return embedding
    
    def batch_encode(
        self,
        texts: List[str],
        batch_size: int = 32,
        show_progress: bool = True
    ) -> np.ndarray:
        """Toplu embedding hesaplama"""
        from tqdm import tqdm
        
        all_embeddings = []
        
        iterator = range(0, len(texts), batch_size)
        if show_progress:
            iterator = tqdm(iterator, desc="Encoding")
        
        for i in iterator:
            batch = texts[i:i + batch_size]
            embeddings = self.encode(batch)
            all_embeddings.append(embeddings)
        
        return np.vstack(all_embeddings)
    
    # =========================================================================
    # FAISS INDEX
    # =========================================================================
    
    def build_index(
        self,
        texts: List[str],
        ids: List[str] = None,
        index_type: str = "flat"
    ):
        """
        FAISS index oluştur
        
        Args:
            texts: İndekslenecek metinler
            ids: Entity ID'leri (opsiyonel)
            index_type: "flat" veya "ivf"
        """
        try:
            import faiss
        except ImportError:
            raise PredictionError("faiss-cpu paketi yüklü değil")
        
        # Embedding'leri hesapla
        embeddings = self.batch_encode(texts)
        d = embeddings.shape[1]
        
        # Index oluştur
        if index_type == "flat":
            self._index = faiss.IndexFlatIP(d)  # Inner product (cosine için normalize edilmiş)
        elif index_type == "ivf":
            nlist = min(100, len(texts) // 10)
            quantizer = faiss.IndexFlatIP(d)
            self._index = faiss.IndexIVFFlat(quantizer, d, nlist)
            self._index.train(embeddings)
        
        # Embedding'leri ekle
        self._index.add(embeddings)
        
        # ID mapping
        if ids:
            self._id_map = {i: id_ for i, id_ in enumerate(ids)}
        else:
            self._id_map = {i: texts[i] for i in range(len(texts))}
        
        logger.info(f"FAISS index oluşturuldu: {len(texts)} vektör")
    
    def search(
        self,
        query: str,
        k: int = 10,
        threshold: float = 0.0
    ) -> List[Tuple[str, float]]:
        """
        En benzer vektörleri bul
        
        Returns:
            [(entity_id, similarity_score)]
        """
        if self._index is None:
            raise PredictionError("Index oluşturulmamış. build_index() çağırın.")
        
        # Query embedding
        query_embedding = self.encode(query).reshape(1, -1)
        
        # Arama
        scores, indices = self._index.search(query_embedding, k)
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and score >= threshold:
                entity_id = self._id_map.get(idx, str(idx))
                results.append((entity_id, float(score)))
        
        return results
    
    def batch_search(
        self,
        queries: List[str],
        k: int = 10
    ) -> List[List[Tuple[str, float]]]:
        """Toplu arama"""
        if self._index is None:
            raise PredictionError("Index oluşturulmamış")
        
        query_embeddings = self.batch_encode(queries, show_progress=False)
        scores, indices = self._index.search(query_embeddings, k)
        
        results = []
        for i in range(len(queries)):
            query_results = []
            for score, idx in zip(scores[i], indices[i]):
                if idx >= 0:
                    entity_id = self._id_map.get(idx, str(idx))
                    query_results.append((entity_id, float(score)))
            results.append(query_results)
        
        return results
    
    # =========================================================================
    # BENZERLİK HESAPLAMA
    # =========================================================================
    
    def similarity(self, text1: str, text2: str) -> float:
        """İki metin arasındaki kosinüs benzerliği"""
        emb1 = self.get_embedding(text1)
        emb2 = self.get_embedding(text2)
        
        return float(np.dot(emb1, emb2))
    
    def pairwise_similarity(self, texts: List[str]) -> np.ndarray:
        """Tüm çiftler arası benzerlik matrisi"""
        embeddings = self.batch_encode(texts)
        return np.dot(embeddings, embeddings.T)
    
    def find_similar(
        self,
        query: str,
        candidates: List[str],
        top_k: int = 5
    ) -> List[Tuple[str, float]]:
        """Aday listesinde en benzerleri bul"""
        query_emb = self.get_embedding(query)
        candidate_embs = self.batch_encode(candidates, show_progress=False)
        
        similarities = np.dot(candidate_embs, query_emb)
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        return [(candidates[i], float(similarities[i])) for i in top_indices]
    
    # =========================================================================
    # KAYDETME / YÜKLEME
    # =========================================================================
    
    def save(self, name: str):
        """Index ve cache'i kaydet"""
        base_path = self.cache_dir / name
        
        # FAISS index
        if self._index is not None:
            import faiss
            faiss.write_index(self._index, str(base_path.with_suffix('.index')))
        
        # ID map ve cache
        data = {
            "id_map": self._id_map,
            "embedding_cache": self._embedding_cache
        }
        with open(base_path.with_suffix('.pkl'), 'wb') as f:
            pickle.dump(data, f)
        
        logger.info(f"Embedding manager kaydedildi: {name}")
    
    def load(self, name: str):
        """Index ve cache'i yükle"""
        base_path = self.cache_dir / name
        
        # FAISS index
        index_path = base_path.with_suffix('.index')
        if index_path.exists():
            import faiss
            self._index = faiss.read_index(str(index_path))
        
        # ID map ve cache
        pkl_path = base_path.with_suffix('.pkl')
        if pkl_path.exists():
            with open(pkl_path, 'rb') as f:
                data = pickle.load(f)
            self._id_map = data.get("id_map", {})
            self._embedding_cache = data.get("embedding_cache", {})
        
        logger.info(f"Embedding manager yüklendi: {name}")
    
    def clear_cache(self):
        """Embedding cache'ini temizle"""
        self._embedding_cache.clear()
        logger.debug("Embedding cache temizlendi")
    
    @property
    def index_size(self) -> int:
        """Index'teki vektör sayısı"""
        return self._index.ntotal if self._index else 0
