"""
ATIK AI - Özel Exception Sınıfları
"""


class AtikAIError(Exception):
    """Temel ATIK AI hatası"""
    def __init__(self, message: str, code: str = None, details: dict = None):
        self.message = message
        self.code = code or "ATIK_ERROR"
        self.details = details or {}
        super().__init__(self.message)


class DatabaseError(AtikAIError):
    """Veritabanı hatası"""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, "DB_ERROR", details)


class ValidationError(AtikAIError):
    """Veri doğrulama hatası"""
    def __init__(self, message: str, field: str = None, details: dict = None):
        self.field = field
        super().__init__(message, "VALIDATION_ERROR", details)


class MatchingError(AtikAIError):
    """Eşleştirme hatası"""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, "MATCHING_ERROR", details)


class FeasibilityError(AtikAIError):
    """Ekonomik fizibilite hatası"""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, "FEASIBILITY_ERROR", details)


class DistanceError(AtikAIError):
    """Mesafe hesaplama hatası"""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, "DISTANCE_ERROR", details)


class KnowledgeGraphError(AtikAIError):
    """Bilgi grafiği hatası"""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, "KNOWLEDGE_GRAPH_ERROR", details)


class PredictionError(AtikAIError):
    """Tahminleme hatası"""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, "PREDICTION_ERROR", details)


class AgentError(AtikAIError):
    """Agent hatası"""
    def __init__(self, message: str, agent_name: str = None, details: dict = None):
        self.agent_name = agent_name
        super().__init__(message, "AGENT_ERROR", details)


class ConfigurationError(AtikAIError):
    """Konfigürasyon hatası"""
    def __init__(self, message: str, config_key: str = None, details: dict = None):
        self.config_key = config_key
        super().__init__(message, "CONFIG_ERROR", details)
