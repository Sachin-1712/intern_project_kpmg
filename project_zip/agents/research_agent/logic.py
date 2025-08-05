from crewai import Agent
from textwrap import dedent
import os
import requests
import base64
from base_agent_logic import BaseAgentLogic
from utils.llm_wrapper import CrewCompatibleLLM
import inspect

class ResearchAgentLogic(BaseAgentLogic):
    def __init__(self):
        self.llm = CrewCompatibleLLM()
        self.token = os.getenv("GITHUB_PAT")
        self.username = os.getenv("GITHUB_USERNAME")
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.agent = Agent(
            role="Research Assistant",
            goal="Efficiently summarize repositories, explore technical documents, and extract insights from GitHub projects.",
            backstory=dedent("""
                You are a skilled research agent specializing in exploring code repositories, summarizing technical documents, and searching GitHub for projects. 
                Your job is to help developers quickly understand and navigate complex projects or files by generating concise summaries and useful insights.
            """),
            allow_delegation=False,
            verbose=True
        )

    def run(self, raw_input: str, parsed_command: dict) -> dict:
        action = parsed_command.get("action")
        params = parsed_command.get("params", {})
        
        # Correct the method name from summarize_repo to summarize_repository
        if action == "summarize_repository":
            return self.summarize_repository(**params)
        elif action == "doc_search":
            return self.doc_search(**params)
        elif action == "search_projects":
            return self.search_projects(**params)
        # We removed get_file_content from this agent in previous steps
        # If you need it, it can be added back, but for now it's removed to avoid conflicts.
        else:
            return {"result": f"[ResearchAgent Error] Unknown action: {action}"}

    def summarize_repository(self, repo_name: str) -> dict:
        """Fetches and summarizes details of a specific GitHub repository."""
        full_repo_name = repo_name if '/' in repo_name else f"{self.username}/{repo_name}"

        try:
            repo_details = self._get_repo_details(full_repo_name)
            repo_contents = self._get_repo_contents(full_repo_name)

            summary = [
                f"**Repository Summary for `{full_repo_name}`**",
                f"**Description:** {repo_details.get('description', 'N/A')}",
                f"**Visibility:** {'Private' if repo_details.get('private') else 'Public'}",
                f"**Primary Language:** {repo_details.get('language', 'N/A')}",
                f"**Stars:** {repo_details.get('stargazers_count', 0)} | **Forks:** {repo_details.get('forks_count', 0)}"
            ]

            if repo_contents:
                summary.append("\n**Files and Folders at root:**")
                for item in repo_contents:
                    item_type = "📁" if item['type'] == 'dir' else "📄"
                    summary.append(f"- {item_type} {item['name']}")

            return {"result": "\n".join(summary)}

        except Exception as e:
            return {"result": f"Could not summarize repository `{full_repo_name}`. Error: {e}"}

    # --- ✨ ADD THIS MISSING METHOD BACK ---
    def _get_repo_details(self, full_repo_name: str) -> dict:
        """Helper to get main repository data."""
        url = f"https://api.github.com/repos/{full_repo_name}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
    # --- END OF ADDED METHOD ---

    def _get_repo_contents(self, full_repo_name: str) -> list:
        """Helper to get repository contents at the root."""
        url = f"https://api.github.com/repos/{full_repo_name}/contents/"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def doc_search(self, repo: str, file: str) -> dict:
        """Finds and summarizes a specific file within a repository."""
        full_repo_name = repo if '/' in repo else f"{self.username}/{repo}"
        try:
            matches = self._find_file_in_repo(full_repo_name, file)
            if not matches:
                return {"result": f"No file named `{file}` found in `{full_repo_name}`."}
            
            summaries = [f"Found {len(matches)} match(es) for `{file}` in `{full_repo_name}`:"]
            for match_path in matches:
                summary_result = self._summarize_file(full_repo_name, match_path)
                summaries.append(f"\n**{match_path}**\n{summary_result['result']}")
            
            return {"result": "\n".join(summaries)}
        except Exception as e:
            return {"result": f"Error during file search: {e}"}

    def _summarize_file(self, repo: str, filepath: str) -> dict:
        """Fetches a file's content from GitHub and uses an LLM to summarize it."""
        url = f"https://api.github.com/repos/{repo}/contents/{filepath}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            file_data = response.json()
            
            content_b64 = file_data.get('content', '')
            decoded_content = base64.b64decode(content_b64).decode('utf-8')

            summarization_prompt = f"Please provide a concise summary of the following file content from the file '{filepath}':\n\n---\n{decoded_content[:4000]}\n---" # Truncate for safety
            summary = self.llm.call([{"role": "user", "content": summarization_prompt}])
            
            return {"result": summary}

        except Exception as e:
            print(f"[ERROR] Failed to fetch or summarize file {filepath} in {repo}: {e}")
            return {"result": f"Could not summarize the file. Error: {e}"}

    def _find_file_in_repo(self, repo: str, filename: str) -> list:
        """Recursively finds all files in a repo that match a filename."""
        url = f"https://api.github.com/repos/{repo}/git/trees/HEAD?recursive=1"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        tree = response.json().get("tree", [])
        return [item["path"] for item in tree if item["type"] == "blob" and item["path"].endswith(filename)]

    def search_projects(self, topic: str) -> dict:
        """Searches all of GitHub for projects related to a topic."""
        url = f"https://api.github.com/search/repositories?q={topic}"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            items = response.json().get("items", [])[:5]
            results = "\n".join([
                f"[{item['full_name']}]({item['html_url']})"
                for item in items
            ])
            return {"result": f"Top 5 GitHub projects on '{topic}':\n{results}"}
        except Exception as e:
            return {"result": f"GitHub project search failed: {e}", "error": str(e)}

    def show_capabilities(self) -> dict:
        """Dynamically lists the capabilities of this agent from its public methods."""
        capabilities = {}
        for name, method in inspect.getmembers(self, inspect.ismethod):
            # Exclude private methods and the capabilities method itself
            if not name.startswith('_') and name not in ['show_capabilities', 'normalize_params', 'run']:
                doc = inspect.getdoc(method)
                description = doc.split('\n')[0] if doc else "No description available."
                capabilities[name] = description
        return {
            "result": "I can perform research by summarizing code repositories and searching documents.",
            "capabilities": capabilities 
        }