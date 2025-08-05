from typing import Any, Dict
from utils.github_client import GitHubClient
from mcp.base import BaseMCP


class GitHubServer(BaseMCP):
    domain = "github"

    def __init__(self) -> None:
        self.client = GitHubClient()

    def capabilities(self) -> str:
        return "GitHub - create_repo, push_file, issues, pull_requests"

    def execute(self, action: str, params: Dict[str, Any]) -> str:
        params = params.copy()
        params.setdefault("name", params.pop("repo_name", None))
        params.setdefault("file_path", params.pop("file_name", None))

        if not hasattr(self.client, action):
            return f"unknown GitHub action {action}"
        return getattr(self.client, action)(
            **{k: v for k, v in params.items() if v is not None}
        )
