"""
ATIK AI - Multi-Agent System Module (Agno Framework)

Agno tabanli coklu ajan sistemi.

Temel Kullanim:
    # Team ile (onerilen)
    from atik_ai.agents import create_atik_team
    team = create_atik_team()
    team.print_response("Plastik atik icin alici bul")

    # Tek ajan ile
    from atik_ai.agents import create_extraction_agent
    agent = create_extraction_agent()
    agent.print_response("EWC 15 01 01 nedir?")

    # Orchestrator ile
    from atik_ai.agents import AtikAIOrchestrator
    orchestrator = AtikAIOrchestrator()
    orchestrator.full_analysis("Tesis analizi yap")

Backward Compatibility:
    Eski API hala destekleniyor ama Agno wrapper'lar uzerinden calisiyor.
"""

# Base classes and data types
from .base import (
    AgentRole,
    WorkflowState,
    ExtractionResult,
    MatchResult,
    FeasibilityResult,
    WorkflowResult,
    AtikAIState,
)

# Agno Agent Factories (RECOMMENDED)
from .agents import (
    create_extraction_agent,
    create_matching_agent,
    create_feasibility_agent,
    create_coordinator_agent,
    create_agent,
    get_extraction_agent,
    get_matching_agent,
    get_feasibility_agent,
    get_coordinator_agent,
    get_default_model,
    get_azure_model,
    AGENT_REGISTRY,
    EXTRACTION_INSTRUCTIONS,
    MATCHING_INSTRUCTIONS,
    FEASIBILITY_INSTRUCTIONS,
    COORDINATOR_INSTRUCTIONS,
)

# Agno Team and Workflows (RECOMMENDED)
from .team import (
    AtikAIOrchestrator,
    AtikAITeamMode,
    create_atik_team,
    create_matching_team,
    create_research_team,
    create_full_analysis_workflow,
    create_quick_match_workflow,
    get_orchestrator,
    reset_orchestrator,
)

# Tools
from .tools import (
    # Extraction tools
    search_similar_facilities,
    search_similar_waste,
    # Matching tools
    find_waste_matches,
    check_technical_compatibility,
    check_temporal_compatibility,
    # Feasibility tools
    analyze_economic_feasibility,
    calculate_transport_cost,
    calculate_pricing,
    # Database tools
    get_facility_info,
    get_waste_type_info,
    list_facilities_by_nace,
    # Distance tools
    calculate_distance,
    # Tool collections
    EXTRACTION_TOOLS,
    MATCHING_TOOLS,
    FEASIBILITY_TOOLS,
    ALL_TOOLS,
)

# Deprecated: Wrapper files removed. Use Agno directly.
# All functionality is available via:
# - AtikAIOrchestrator for orchestration
# - create_*_agent() factories for individual agents
# - create_*_team() factories for team workflows


__all__ = [
    # === AGNO (Recommended) ===
    # Agent Factories
    "create_extraction_agent",
    "create_matching_agent",
    "create_feasibility_agent",
    "create_coordinator_agent",
    "create_agent",
    "get_extraction_agent",
    "get_matching_agent",
    "get_feasibility_agent",
    "get_coordinator_agent",
    "get_default_model",
    "get_azure_model",
    
    # Team & Workflows
    "AtikAIOrchestrator",
    "AtikAITeamMode",
    "create_atik_team",
    "create_matching_team",
    "create_research_team",
    "create_full_analysis_workflow",
    "create_quick_match_workflow",
    "get_orchestrator",
    "reset_orchestrator",
    
    # Tools
    "search_knowledge_graph",
    "find_waste_matches",
    "analyze_economic_feasibility",
    "calculate_distance",
    "EXTRACTION_TOOLS",
    "MATCHING_TOOLS",
    "FEASIBILITY_TOOLS",
    "ALL_TOOLS",
    
    # === DATA TYPES ===
    "AgentRole",
    "WorkflowState",
    "ExtractionResult",
    "MatchResult",
    "FeasibilityResult",
    "WorkflowResult",
    "AtikAIState",
    
    # Instructions
    "EXTRACTION_INSTRUCTIONS",
    "MATCHING_INSTRUCTIONS",
    "FEASIBILITY_INSTRUCTIONS",
    "COORDINATOR_INSTRUCTIONS",
    "AGENT_REGISTRY",
]
