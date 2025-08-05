
from typing import Any, Dict
from agents.jira_agent.logic import JiraAgentLogic
from mcp.base import BaseMCP

class JiraServer(BaseMCP):
    domain = "jira"

    def __init__(self) -> None:
        self.logic = JiraAgentLogic()

    def capabilities(self) -> str:
        return "Jira – create_project, create_ticket, get_ticket"

    def execute(self, action: str, params: Dict[str, Any]) -> str:
        if not hasattr(self.logic, action):
            return f"[JiraServer Error] Unknown action: {action}"

        try:
            normalized = self.logic.normalize_params(action, params)
            return getattr(self.logic, action)(**normalized)
        except Exception as e:
            return f"[JiraServer Error] Failed to execute '{action}': {e}"
