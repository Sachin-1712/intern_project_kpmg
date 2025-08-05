import os
import json
import base64
import inspect
import requests
from dotenv import load_dotenv
from crewai import Agent
import streamlit as st

# Make sure these import paths are correct for your project structure
from utils.llm_wrapper import CrewCompatibleLLM
from agents.developer_agent.logic import DeveloperAgentLogic
from base_agent_logic import BaseAgentLogic


class GitAgentLogic(BaseAgentLogic):
    def __init__(self):
        load_dotenv()
        self.dev = DeveloperAgentLogic()
        self.llm = CrewCompatibleLLM()
        self.base_url = "https://api.github.com"
        self.username = os.getenv("GITHUB_USERNAME")
        self.token = os.getenv("GITHUB_PAT", "").strip()
        self.default_branch = os.getenv("GITHUB_DEFAULT_BRANCH", "main")

        if not self.token or not self.username:
            raise EnvironmentError("GITHUB_PAT and GITHUB_USERNAME environment variables must be set.")

        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json"
        }

        self.agent = Agent(
            role="GitHub DevOps Assistant",
            goal="To automate GitHub operations such as repo creation, file pushes, issue tracking, and PRs.",
            backstory=(
                "You are a GitHub-savvy AI DevOps assistant built to help developers automate GitHub actions like "
                "creating repositories, committing files, tracking issues, and managing pull requests. You ensure smooth "
                "and efficient CI/CD workflows by handling all GitHub API operations accurately."
            ),
            allow_delegation=False,
            verbose=True,
            llm=self.llm
        )

    def normalize_params(self, action, params, raw_input=None):
        if action == "push_file" and "content" not in params and "task" in params:
            if "language" not in params:
                return params, action, ["language"]
            
            print("[INFO][GitAgent] 'task' provided without content. Generating code with DeveloperAgent.")
            code_result = self.dev.generate_code(params["language"], params["task"])
            params["content"] = code_result.get("code", code_result.get("result", ""))

        if "code" in params and "content" not in params:
            params["content"] = params.pop("code")

        if action == "push_file" and "file_path" not in params and "file_name" in params:
            params["file_path"] = params.pop("file_name")
        
        if action == "push_file":
            params.pop("language", None)
            params.pop("task", None)

        method = getattr(self, action, None)
        missing = []
        if callable(method):
            sig = inspect.signature(method)
            for param in sig.parameters.values():
                if param.default == inspect.Parameter.empty and param.name not in params:
                    missing.append(param.name)

        return params, action, missing

    def create_repo(self, repo_name: str, private: bool = False):
        """Create a new GitHub repository."""
        url = f"{self.base_url}/user/repos"
        data = { "name": repo_name, "private": private, "auto_init": True }
        try:
            response = requests.post(url, headers=self.headers, json=data)
            response.raise_for_status()
            repo_data = response.json()
            return {
                "result": f"Repo created: {repo_data['html_url']}",
                "link": repo_data['html_url']
            }
        except requests.exceptions.HTTPError as e:
             if e.response.status_code == 422:
                 return {"result": f"Repo '{repo_name}' already exists.", "error": "Repository already exists."}
             return {"result": f"Repo creation failed: {e}", "error": str(e)}
        except Exception as e:
            return {"result": f"Repo creation failed: {e}", "error": str(e)}

    def list_repos(self):
        """List all repositories for the authenticated GitHub user."""
        url = f"{self.base_url}/user/repos"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            repos = response.json()
            names = [repo['name'] for repo in repos]
            
            # --- ✨ CORRECTED FORMATTING ---
            if not names:
                return {"result": "You have no repositories."}
            
            bullet_points = "\n".join([f"- {name}" for name in names])
            return {"result": f"Here are your repositories:\n{bullet_points}"}
            # --- END CORRECTION ---

        except Exception as e:
            return {"result": f"Failed to list repositories: {e}", "error": str(e)}

    def get_file_content(self, repo_name: str, file_path: str, branch: str = None):
        """Gets the content of a file from a GitHub repository."""
        if branch is None:
            branch = self.default_branch
        url = f"{self.base_url}/repos/{self.username}/{repo_name}/contents/{file_path}?ref={branch}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            file_data = response.json()
            
            if file_data.get('encoding') != 'base64':
                return {"result": "File content encoding not supported.", "error": "unsupported_encoding"}

            decoded_content = base64.b64decode(file_data['content']).decode('utf-8')
            return {
                "result": f"Successfully retrieved content for '{file_path}'.",
                "content": decoded_content,
                "sha": file_data.get('sha')
            }
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return {"result": f"File '{file_path}' not found.", "error": "File not found."}
            return {"result": f"Failed to get file content: {e}", "error": str(e)}
        except Exception as e:
            return {"result": f"Failed to get file content: {e}", "error": str(e)}
            
    def open_interactive_editor(self, repo_name: str, file_path: str, branch: str = None):
        """
        Fetches file content and sets a flag in session_state to open the Streamlit editor dialog.
        """
        print(f"[INFO] Fetching {file_path} to open in Streamlit editor...")
        get_result = self.get_file_content(repo_name=repo_name, file_path=file_path, branch=branch)
        
        if get_result.get("error"):
            st.error(get_result["result"])
            return

        st.session_state.code_to_edit = get_result["content"]
        st.session_state.file_to_edit_path = file_path
        st.session_state.repo_to_edit = repo_name
        st.session_state.sha_to_edit = get_result.get("sha")
        st.session_state.show_editor_dialog = True

    def push_file(self, repo_name: str, file_path: str, content: str, commit_message: str = "Auto-commit by AI Agent", branch: str = None, sha: str = None):
        """Pushes a file to a GitHub repository, creating or updating it."""
        if branch is None:
            branch = self.default_branch

        url = f"{self.base_url}/repos/{self.username}/{repo_name}/contents/{file_path}"
        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")

        data = {"message": commit_message, "content": encoded_content, "branch": branch}
        
        if not sha:
            try:
                get_file_response = requests.get(f"{url}?ref={branch}", headers=self.headers)
                if get_file_response.status_code == 200:
                    sha = get_file_response.json().get("sha")
            except requests.RequestException:
                pass

        if sha:
            data["sha"] = sha

        try:
            response = requests.put(url, headers=self.headers, json=data)
            response.raise_for_status()
            file_data = response.json()
            return {
                "result": f"File '{file_path}' pushed to repo '{repo_name}'",
                "link": file_data.get("content", {}).get("html_url")
            }
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print(f"[INFO] Repo '{repo_name}' not found. Attempting to create it first.")
                creation_result = self.create_repo(repo_name)
                if "error" in creation_result and "already exists" not in creation_result["error"]:
                    return {"result": f"Could not create repo '{repo_name}': {creation_result.get('error')}", "error": creation_result.get('error')}
                return self.push_file(repo_name, file_path, content, commit_message, branch)
            return {"result": f"File push failed: {e}", "error": str(e)}
        except Exception as e:
            return {"result": f"File push failed: {e}", "error": str(e)}

    def create_issue(self, repo_name: str, title: str, body: str):
        """Create an issue in a GitHub repository."""
        url = f"{self.base_url}/repos/{self.username}/{repo_name}/issues"
        data = {"title": title, "body": body}
        try:
            response = requests.post(url, headers=self.headers, json=data)
            response.raise_for_status()
            issue_data = response.json()
            return {
                "result": f"Issue created: {issue_data['html_url']}",
                "link": issue_data['html_url']
            }
        except Exception as e:
            return {"result": f"Issue creation failed: {e}", "error": str(e)}

    def delete_repo(self, repo_name: str):
        """Delete an existing GitHub repository."""
        url = f"{self.base_url}/repos/{self.username}/{repo_name}"
        try:
            response = requests.delete(url, headers=self.headers)
            response.raise_for_status()
            return {"result": f"Repository '{repo_name}' deleted."}
        except Exception as e:
            return {"result": f"Repo deletion failed: {e}", "error": str(e)}

    def create_pull_request(self, repo_name: str, title: str, head_branch: str, base_branch: str = "main", body: str = ""):
        """Create a pull request on a GitHub repository."""
        url = f"{self.base_url}/repos/{self.username}/{repo_name}/pulls"
        data = {"title": title, "head": head_branch, "base": base_branch, "body": body}
        try:
            response = requests.post(url, headers=self.headers, json=data)
            response.raise_for_status()
            pr_data = response.json()
            return {
                "result": f"Pull request created: {pr_data['html_url']}",
                "link": pr_data['html_url']
            }
        except Exception as e:
            return {"result": f"PR creation failed: {e}", "error": str(e)}
    
    def create_branch(self, repo_name: str, new_branch_name: str, source_branch: str = None):
        """Creates a new branch in a repository from a source branch."""
        if source_branch is None:
            source_branch = self.default_branch
        
        ref_url = f"{self.base_url}/repos/{self.username}/{repo_name}/git/ref/heads/{source_branch}"
        try:
            ref_response = requests.get(ref_url, headers=self.headers)
            ref_response.raise_for_status()
            source_sha = ref_response.json()['object']['sha']
        except requests.exceptions.HTTPError as e:
            return {"result": f"Could not find source branch '{source_branch}'. Error: {e}", "error": str(e)}

        create_ref_url = f"{self.base_url}/repos/{self.username}/{repo_name}/git/refs"
        data = {"ref": f"refs/heads/{new_branch_name}", "sha": source_sha}
        try:
            response = requests.post(create_ref_url, headers=self.headers, json=data)
            response.raise_for_status()
            
            branch_link = f"https://github.com/{self.username}/{repo_name}/tree/{new_branch_name}"
            return {
                "result": f"Successfully created branch '{new_branch_name}'.",
                "link": branch_link
            }
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 422:
                return {"result": f"Branch '{new_branch_name}' already exists.", "error": "Branch already exists."}
            return {"result": f"Branch creation failed: {e}", "error": str(e)}
    
    def list_branches(self, repo_name: str):
        """Lists all branches in a specified repository."""
        url = f"{self.base_url}/repos/{self.username}/{repo_name}/branches"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            branches = response.json()
            branch_names = [branch['name'] for branch in branches]
            
            # --- ✨ CORRECTED FORMATTING ---
            if not branch_names:
                return {"result": f"No branches found in repo '{repo_name}'."}

            bullet_points = "\n".join([f"- {name}" for name in branch_names])
            return {"result": f"Branches in '{repo_name}':\n{bullet_points}"}
            # --- END CORRECTION ---

        except requests.exceptions.HTTPError as e:
            return {"result": f"Could not list branches for '{repo_name}'. Error: {e}", "error": str(e)}
    
    def merge_branch(self, repo_name: str, head_branch: str, base_branch: str = None, commit_message: str = None):
        """Merges a head branch into a base branch."""
        if base_branch is None:
            base_branch = self.default_branch
        
        if commit_message is None:
            commit_message = f"Merge branch '{head_branch}' into '{base_branch}'"

        url = f"{self.base_url}/repos/{self.username}/{repo_name}/merges"
        data = {"base": base_branch, "head": head_branch, "commit_message": commit_message}
        try:
            response = requests.post(url, headers=self.headers, json=data)
            
            if response.status_code == 201:
                merge_data = response.json()
                return {
                    "result": f"Successfully merged '{head_branch}' into '{base_branch}'.",
                    "link": merge_data['html_url']
                }
            elif response.status_code == 204:
                return {"result": f"Nothing to merge. '{head_branch}' is already up-to-date."}
            
            response.raise_for_status()
            return {"result": "Merge completed with an unexpected status."}

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 409:
                return {"result": f"Merge conflict! Could not merge '{head_branch}'.", "error": "Merge conflict"}
            elif e.response.status_code == 404:
                return {"result": f"Merge failed. Branch not found.", "error": "Branch not found"}
            return {"result": f"Merge failed: {e}", "error": str(e)}
            
    def delete_branch(self, repo_name: str, branch_name: str):
        """Deletes a branch from the repository."""
        if branch_name == self.default_branch:
            return {"result": f"Cannot delete the default branch '{branch_name}'.", "error": "Cannot delete default branch"}

        url = f"{self.base_url}/repos/{self.username}/{repo_name}/git/refs/heads/{branch_name}"
        try:
            response = requests.delete(url, headers=self.headers)
            response.raise_for_status()
            return {"result": f"Successfully deleted branch '{branch_name}' from repo '{repo_name}'."}
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return {"result": f"Branch '{branch_name}' not found.", "error": "Branch not found"}
            return {"result": f"Failed to delete branch: {e}", "error": str(e)}
    
    def show_capabilities(self) -> dict:
        """Dynamically lists the capabilities of this agent."""
        capabilities = {}
        for name, method in inspect.getmembers(self, inspect.ismethod):
            if not name.startswith('_') and name not in ['show_capabilities', 'normalize_params', 'run']:
                doc = inspect.getdoc(method)
                description = doc.split('\n')[0] if doc else "No description."
                capabilities[name] = description

        return {
            "result": "I can manage GitHub repositories, files, issues, and pull requests.",
            "capabilities": capabilities 
        }