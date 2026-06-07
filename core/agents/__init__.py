# core/agents/__init__.py
from .agent_manager import AgentManager
from .critic import SelfCritiqueLoop
from .document_agent import DocumentAgent
from .email_agent import EmailAgent
from .planner_agent import ResearchPlannerAgent
from .self_improvement import SkillFactory

__all__ = [
    "AgentManager", "SelfCritiqueLoop", "DocumentAgent", "EmailAgent",
    "ResearchPlannerAgent", "SkillFactory",
]
