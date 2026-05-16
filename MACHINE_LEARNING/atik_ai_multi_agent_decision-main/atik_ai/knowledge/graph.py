"""
ATIK AI - Knowledge Graph (PostgreSQL)
W2RKG: Waste-to-Resource Knowledge Graph stored in w2rkg_library table

İlişkiler (relational):
Waste -> Process -> Resource (W-P-R triples)
"""
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from ..core.database import get_db
from ..core.exceptions import KnowledgeGraphError

logger = logging.getLogger(__name__)


@dataclass
class Triple:
    """Waste-Process-Resource üçlüsü"""
    waste: str
    process: str
    resource: str
    doi: Optional[str] = None
    confidence: float = 1.0
    
    def to_dict(self) -> dict:
        return {
            "waste": self.waste,
            "process": self.process,
            "resource": self.resource,
            "doi": self.doi,
            "confidence": self.confidence
        }


@dataclass
class GraphNode:
    """Graf düğümü"""
    id: str
    name: str
    node_type: str  # Waste, Process, Resource
    embedding: Optional[List[float]] = None
    properties: Optional[dict] = None


class KnowledgeGraph:
    """
    Atıktan-Kaynağa Bilgi Grafiği (W2RKG)
    
    PostgreSQL tabanlı w2rkg_library işlemleri
    """
    
    def __init__(self):
        self.db = get_db()
    
    # =========================================================================
    # DÜĞÜM İŞLEMLERİ
    # =========================================================================
    
    def add_waste(self, name: str, ewc_code: str = None, embedding: List[float] = None) -> str:
        """Atık düğümü ekle"""
        query = """
        MERGE (w:Waste {name: $name})
        SET w.ewc_code = $ewc_code,
            w.embedding = $embedding,
            w.updated_at = datetime()
        RETURN w.name as id
        """
        result = self.db.run_cypher(query, {
            "name": name,
            "ewc_code": ewc_code,
            "embedding": embedding
        })
        return result[0]["id"] if result else None
    
    def add_process(self, name: str, description: str = None, embedding: List[float] = None) -> str:
        """Süreç düğümü ekle"""
        query = """
        MERGE (p:Process {name: $name})
        SET p.description = $description,
            p.embedding = $embedding,
            p.updated_at = datetime()
        RETURN p.name as id
        """
        result = self.db.run_cypher(query, {
            "name": name,
            "description": description,
            "embedding": embedding
        })
        return result[0]["id"] if result else None
    
    def add_resource(self, name: str, cpc_code: str = None, embedding: List[float] = None) -> str:
        """Kaynak düğümü ekle"""
        query = """
        MERGE (r:Resource {name: $name})
        SET r.cpc_code = $cpc_code,
            r.embedding = $embedding,
            r.updated_at = datetime()
        RETURN r.name as id
        """
        result = self.db.run_cypher(query, {
            "name": name,
            "cpc_code": cpc_code,
            "embedding": embedding
        })
        return result[0]["id"] if result else None
    
    # =========================================================================
    # İLİŞKİ İŞLEMLERİ
    # =========================================================================
    
    def add_triple(self, triple: Triple) -> bool:
        """
        W-P-R üçlüsü ekle
        
        (Waste)-[:TRANSFORMED_BY]->(Process)-[:BECOMES]->(Resource)
        """
        query = """
        MERGE (w:Waste {name: $waste})
        MERGE (p:Process {name: $process})
        MERGE (r:Resource {name: $resource})
        MERGE (w)-[t:TRANSFORMED_BY]->(p)
        MERGE (p)-[b:BECOMES]->(r)
        SET t.doi = $doi, t.confidence = $confidence,
            b.doi = $doi, b.confidence = $confidence
        RETURN w.name, p.name, r.name
        """
        try:
            result = self.db.run_cypher(query, triple.to_dict())
            logger.debug(f"Triple eklendi: {triple.waste} -> {triple.resource}")
            return len(result) > 0
        except Exception as e:
            raise KnowledgeGraphError(f"Triple ekleme hatası: {e}")
    
    def add_triples_batch(self, triples: List[Triple]) -> int:
        """Toplu triple ekleme"""
        query = """
        UNWIND $triples as t
        MERGE (w:Waste {name: t.waste})
        MERGE (p:Process {name: t.process})
        MERGE (r:Resource {name: t.resource})
        MERGE (w)-[tr:TRANSFORMED_BY]->(p)
        MERGE (p)-[b:BECOMES]->(r)
        SET tr.doi = t.doi, tr.confidence = t.confidence,
            b.doi = t.doi, b.confidence = t.confidence
        RETURN count(*) as count
        """
        try:
            result = self.db.run_cypher(query, {
                "triples": [t.to_dict() for t in triples]
            })
            count = result[0]["count"] if result else 0
            logger.info(f"{count} triple eklendi")
            return count
        except Exception as e:
            raise KnowledgeGraphError(f"Batch ekleme hatası: {e}")
    
    # =========================================================================
    # SORGULAR
    # =========================================================================
    
    def find_transformations(self, waste_name: str) -> List[Dict]:
        """
        Bir atığın dönüştürülebileceği kaynakları bul
        
        Returns:
            List of {process, resource, confidence, doi}
        """
        query = """
        MATCH (w:Waste {name: $waste})-[t:TRANSFORMED_BY]->(p:Process)-[b:BECOMES]->(r:Resource)
        RETURN p.name as process, r.name as resource, 
               t.confidence as confidence, t.doi as doi
        ORDER BY t.confidence DESC
        """
        return self.db.run_cypher(query, {"waste": waste_name})
    
    def find_resources(self, waste_name: str) -> List[str]:
        """Atıktan üretilebilecek kaynakları bul"""
        results = self.find_transformations(waste_name)
        return list(set(r["resource"] for r in results))
    
    def find_wastes_for_resource(self, resource_name: str) -> List[Dict]:
        """Bir kaynağı üretmek için kullanılabilecek atıkları bul"""
        query = """
        MATCH (w:Waste)-[t:TRANSFORMED_BY]->(p:Process)-[b:BECOMES]->(r:Resource {name: $resource})
        RETURN w.name as waste, p.name as process,
               t.confidence as confidence, t.doi as doi
        ORDER BY t.confidence DESC
        """
        return self.db.run_cypher(query, {"resource": resource_name})
    
    def find_similar_wastes(self, waste_name: str, limit: int = 10) -> List[Dict]:
        """Benzer atıkları bul (embedding similarity)"""
        query = """
        MATCH (w1:Waste {name: $waste})
        WHERE w1.embedding IS NOT NULL
        MATCH (w2:Waste)
        WHERE w2.name <> w1.name AND w2.embedding IS NOT NULL
        WITH w1, w2, gds.similarity.cosine(w1.embedding, w2.embedding) as similarity
        WHERE similarity > 0.7
        RETURN w2.name as waste, similarity
        ORDER BY similarity DESC
        LIMIT $limit
        """
        return self.db.run_cypher(query, {"waste": waste_name, "limit": limit})
    
    def search_by_text(self, query_text: str, node_type: str = None, limit: int = 20) -> List[Dict]:
        """Metin araması (full-text search)"""
        type_filter = f":{node_type}" if node_type else ""
        query = f"""
        MATCH (n{type_filter})
        WHERE toLower(n.name) CONTAINS toLower($query)
        RETURN labels(n)[0] as type, n.name as name
        LIMIT $limit
        """
        return self.db.run_cypher(query, {"query": query_text, "limit": limit})
    
    # =========================================================================
    # İSTATİSTİKLER
    # =========================================================================
    
    def get_stats(self) -> Dict:
        """Graf istatistikleri"""
        query = """
        MATCH (w:Waste) WITH count(w) as wastes
        MATCH (p:Process) WITH wastes, count(p) as processes
        MATCH (r:Resource) WITH wastes, processes, count(r) as resources
        MATCH ()-[t:TRANSFORMED_BY]->() WITH wastes, processes, resources, count(t) as transformations
        MATCH ()-[b:BECOMES]->() 
        RETURN wastes, processes, resources, transformations, count(b) as becomes
        """
        result = self.db.run_cypher(query)
        return result[0] if result else {}
    
    def get_top_wastes(self, limit: int = 10) -> List[Dict]:
        """En çok dönüşümü olan atıklar"""
        query = """
        MATCH (w:Waste)-[t:TRANSFORMED_BY]->()
        RETURN w.name as waste, count(t) as transformations
        ORDER BY transformations DESC
        LIMIT $limit
        """
        return self.db.run_cypher(query, {"limit": limit})
    
    def get_top_resources(self, limit: int = 10) -> List[Dict]:
        """En çok üretilen kaynaklar"""
        query = """
        MATCH ()-[b:BECOMES]->(r:Resource)
        RETURN r.name as resource, count(b) as productions
        ORDER BY productions DESC
        LIMIT $limit
        """
        return self.db.run_cypher(query, {"limit": limit})
    
    # =========================================================================
    # BAKIMI
    # =========================================================================
    
    def create_indexes(self):
        """Performans için indeksler oluştur"""
        indexes = [
            "CREATE INDEX waste_name IF NOT EXISTS FOR (w:Waste) ON (w.name)",
            "CREATE INDEX process_name IF NOT EXISTS FOR (p:Process) ON (p.name)",
            "CREATE INDEX resource_name IF NOT EXISTS FOR (r:Resource) ON (r.name)",
        ]
        for query in indexes:
            try:
                self.db.run_cypher(query)
            except Exception as e:
                logger.warning(f"Index oluşturma hatası: {e}")
        
        logger.info("Graf indeksleri oluşturuldu")
    
    def clear_all(self):
        """Tüm grafı temizle (DİKKAT!)"""
        query = "MATCH (n) DETACH DELETE n"
        self.db.run_cypher(query)
        logger.warning("Tüm graf silindi!")
