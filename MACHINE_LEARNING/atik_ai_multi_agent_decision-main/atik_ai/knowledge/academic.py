"""
ATIK AI - Academic Data Collector
Scopus, Google Scholar API entegrasyonu

Anahtar kelimeler:
- "industrial symbiosis"
- "waste valorization"
"""
import logging
import time
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime

from ..core.exceptions import AtikAIError

logger = logging.getLogger(__name__)


@dataclass
class Paper:
    """Akademik makale"""
    doi: str
    title: str
    authors: List[str]
    journal: str
    year: int
    abstract: str
    keywords: List[str] = None
    full_text: str = None
    citations: int = 0
    
    def to_dict(self) -> dict:
        return {
            "doi": self.doi,
            "title": self.title,
            "authors": self.authors,
            "journal": self.journal,
            "year": self.year,
            "abstract": self.abstract,
            "keywords": self.keywords or [],
            "citations": self.citations
        }


class AcademicDataCollector:
    """
    Akademik veri toplayıcı
    
    Desteklenen kaynaklar:
    - Scopus API
    - Google Scholar (scholarly)
    - CrossRef
    """
    
    DEFAULT_KEYWORDS = [
        "industrial symbiosis",
        "waste valorization",
        "waste to resource",
        "circular economy waste",
        "by-product exchange"
    ]
    
    def __init__(self, scopus_api_key: str = None):
        self.scopus_api_key = scopus_api_key
        self._scopus_client = None
    
    # =========================================================================
    # SCOPUS
    # =========================================================================
    
    def search_scopus(
        self,
        query: str,
        max_results: int = 100,
        year_from: int = 2015
    ) -> List[Paper]:
        """
        Scopus'ta makale ara
        
        Args:
            query: Arama sorgusu
            max_results: Maksimum sonuç sayısı
            year_from: Başlangıç yılı
        """
        if not self.scopus_api_key:
            logger.warning("Scopus API key yok")
            return []
        
        try:
            from pybliometrics.scopus import ScopusSearch
            
            # Sorgu oluştur
            full_query = f'TITLE-ABS-KEY("{query}") AND PUBYEAR > {year_from}'
            
            search = ScopusSearch(full_query, subscriber=False)
            
            papers = []
            for i, result in enumerate(search.results or []):
                if i >= max_results:
                    break
                
                papers.append(Paper(
                    doi=result.doi or f"scopus_{result.eid}",
                    title=result.title or "",
                    authors=(result.author_names or "").split("; "),
                    journal=result.publicationName or "",
                    year=int(result.coverDate[:4]) if result.coverDate else 0,
                    abstract=result.description or "",
                    citations=result.citedby_count or 0
                ))
            
            logger.info(f"Scopus: {len(papers)} makale bulundu")
            return papers
            
        except ImportError:
            logger.warning("pybliometrics paketi yüklü değil")
            return []
        except Exception as e:
            logger.error(f"Scopus arama hatası: {e}")
            return []
    
    # =========================================================================
    # GOOGLE SCHOLAR
    # =========================================================================
    
    def search_scholar(
        self,
        query: str,
        max_results: int = 50
    ) -> List[Paper]:
        """
        Google Scholar'da makale ara
        
        Not: Rate limiting var, dikkatli kullan
        """
        try:
            from scholarly import scholarly
            
            papers = []
            search_query = scholarly.search_pubs(query)
            
            for i, result in enumerate(search_query):
                if i >= max_results:
                    break
                
                # Rate limiting
                time.sleep(1)
                
                bib = result.get('bib', {})
                
                papers.append(Paper(
                    doi=result.get('pub_url', f"scholar_{i}"),
                    title=bib.get('title', ""),
                    authors=bib.get('author', "").split(" and "),
                    journal=bib.get('venue', ""),
                    year=int(bib.get('pub_year', 0)),
                    abstract=bib.get('abstract', ""),
                    citations=result.get('num_citations', 0)
                ))
            
            logger.info(f"Scholar: {len(papers)} makale bulundu")
            return papers
            
        except ImportError:
            logger.warning("scholarly paketi yüklü değil")
            return []
        except Exception as e:
            logger.error(f"Scholar arama hatası: {e}")
            return []
    
    # =========================================================================
    # CROSSREF
    # =========================================================================
    
    def search_crossref(
        self,
        query: str,
        max_results: int = 100
    ) -> List[Paper]:
        """CrossRef API ile makale ara"""
        import requests
        
        url = "https://api.crossref.org/works"
        params = {
            "query": query,
            "rows": max_results,
            "filter": "type:journal-article",
            "select": "DOI,title,author,container-title,published,abstract"
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            items = data.get("message", {}).get("items", [])
            
            papers = []
            for item in items:
                # Yılı çıkar
                published = item.get("published", {})
                date_parts = published.get("date-parts", [[0]])[0]
                year = date_parts[0] if date_parts else 0
                
                # Yazarları çıkar
                authors = [
                    f"{a.get('given', '')} {a.get('family', '')}".strip()
                    for a in item.get("author", [])
                ]
                
                papers.append(Paper(
                    doi=item.get("DOI", ""),
                    title=item.get("title", [""])[0],
                    authors=authors,
                    journal=item.get("container-title", [""])[0],
                    year=year,
                    abstract=item.get("abstract", "")
                ))
            
            logger.info(f"CrossRef: {len(papers)} makale bulundu")
            return papers
            
        except Exception as e:
            logger.error(f"CrossRef arama hatası: {e}")
            return []
    
    # =========================================================================
    # BİRLEŞİK ARAMA
    # =========================================================================
    
    def collect_papers(
        self,
        keywords: List[str] = None,
        sources: List[str] = None,
        max_per_source: int = 50
    ) -> List[Paper]:
        """
        Tüm kaynaklardan makale topla
        
        Args:
            keywords: Arama anahtar kelimeleri
            sources: Kullanılacak kaynaklar ["scopus", "scholar", "crossref"]
            max_per_source: Kaynak başına maksimum makale
        """
        keywords = keywords or self.DEFAULT_KEYWORDS
        sources = sources or ["crossref"]  # Varsayılan: CrossRef (API key gerekmez)
        
        all_papers = []
        seen_dois = set()
        
        for keyword in keywords:
            logger.info(f"Aranıyor: '{keyword}'")
            
            for source in sources:
                if source == "scopus":
                    papers = self.search_scopus(keyword, max_per_source)
                elif source == "scholar":
                    papers = self.search_scholar(keyword, max_per_source)
                elif source == "crossref":
                    papers = self.search_crossref(keyword, max_per_source)
                else:
                    continue
                
                # Duplicate filtrele
                for paper in papers:
                    if paper.doi and paper.doi not in seen_dois:
                        seen_dois.add(paper.doi)
                        all_papers.append(paper)
        
        logger.info(f"Toplam {len(all_papers)} unique makale toplandı")
        return all_papers
    
    def save_to_database(self, papers: List[Paper], db_session) -> int:
        """Makaleleri veritabanına kaydet"""
        from ..core.models import AcademicSource
        
        count = 0
        for paper in papers:
            try:
                source = AcademicSource(
                    doi=paper.doi,
                    title=paper.title,
                    authors=", ".join(paper.authors),
                    journal=paper.journal,
                    year=paper.year,
                    abstract=paper.abstract,
                    processed=False
                )
                db_session.merge(source)
                count += 1
            except Exception as e:
                logger.warning(f"Kayıt hatası ({paper.doi}): {e}")
        
        db_session.commit()
        logger.info(f"{count} makale kaydedildi")
        return count
