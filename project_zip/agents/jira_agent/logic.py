import os
import base64
import requests
from typing import Dict, Tuple
import inspect
from dotenv import load_dotenv
from crewai import Agent
from textwrap import dedent
from base_agent_logic import BaseAgentLogic
from jira import JIRA
import re


class JiraAgentLogic(BaseAgentLogic):
    def __init__(self):
        load_dotenv()
        self.base_url = os.getenv("JIRA_BASE_URL")
        user_email = os.getenv("JIRA_USER_EMAIL")
        api_token = os.getenv("JIRA_API_TOKEN")

        if not all([self.base_url, user_email, api_token]):
            raise EnvironmentError("Jira environment variables (JIRA_BASE_URL, JIRA_USER_EMAIL, JIRA_API_TOKEN) are not set.")
        self.user_email = user_email
        self.jira = JIRA(
            server=self.base_url,
            basic_auth=(user_email, api_token),
        )
        auth_string = f"{user_email}:{api_token}"
        encoded_auth = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")
        self.headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Accept": "application/json"
        }

        self.headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Accept": "application/json"
        }

        self.agent = Agent(
            role="Jira Manager",
            goal="Efficiently manage Jira projects and issues with clear updates",
            backstory=dedent("""
                You are a software project assistant specialized in Jira.
                Your job is to help engineering teams organize tasks, track progress,
                and provide updates about tickets or projects.
                You understand how to create new projects, raise issues, and retrieve ticket details.
            """),
            allow_delegation=False
        )

    def validate_params(self, action: str, params: dict) -> dict:
        """
        Validates parameters for a given action. Returns a dictionary with validation status.
        """
        if action == "create_project":
            project_key = params.get("project_key")
            # Rule: Project key must be 2-4 uppercase letters.
            if project_key and not re.match(r'^[A-Z]{2,4}$', project_key):
                return {
                    "is_valid": False,
                    "invalid_param": "project_key",
                    "message": f"The project key '{project_key}' is invalid.",
                    "suggestion": "A project key should be 2-4 uppercase letters (e.g., 'PROJ')."
                }
        
        # Add other validation rules for other actions here...

        # If all checks pass, return a success status.
        return {"is_valid": True}

    def run(self, action: str, params: dict):
        method = getattr(self, action, None)
        if method:
            return method(**params)
        return {"result": f"[JiraAgent Error] Unsupported action: {action}"}

    # --- NEW METHODS START HERE ---

    def _get_key_from_name(self, project_name: str) -> str | None:
        """Helper function to find a project key from a project name."""
        print(f"[JiraAgent] Searching for project key for name: '{project_name}'")
        url = f"{self.base_url}/rest/api/3/project"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            projects = response.json()
            
            for project in projects:
                if project.get('name', '').lower() == project_name.lower():
                    project_key = project.get('key')
                    print(f"[JiraAgent] Found matching project key: '{project_key}'")
                    return project_key
            
            print(f"[JiraAgent] No project found with the name '{project_name}'.")
            return None
        except Exception as e:
            print(f"[JiraAgent ERROR] Failed to search for projects: {e}")
            return None

    def normalize_params(self, action: str, params: dict, raw_input: str = None) -> Tuple[dict, str, list]:
        """
        Normalizes parameters for Jira actions, attempting to convert project_name to project_key.
        """
        actions_needing_key = ['create_ticket', 'list_tickets', 'get_ticket']
        
        if action in actions_needing_key and 'project_key' not in params:
            if 'project_name' in params:
                project_key = self._get_key_from_name(params['project_name'])
                if project_key:
                    params['project_key'] = project_key

        method = getattr(self, action, None)
        missing = []
        if callable(method):
            sig = inspect.signature(method)
            for param in sig.parameters.values():
                if param.default == inspect.Parameter.empty and param.name not in params:
                    missing.append(param.name)
                    
        return params, action, missing

    # --- NEW METHODS END HERE ---

    def list_projects(self):
        """List all projects accessible to the authenticated Jira user."""
        url = f"{self.base_url}/rest/api/3/project"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            projects = response.json()
            project_names = [project.get('name') for project in projects]
            
            if not project_names:
                return {"result": "No Jira projects found."}
                
            project_list = "\n".join([f"- {name}" for name in project_names])
            return {"result": f" Here are your Jira Projects:\n{project_list}"}

        except Exception as e:
            return {"result": f" Failed to list Jira projects: {e}", "error": str(e)}
        
    def list_tickets(self, project_name: str = None, project_key: str = None) -> dict:
        """Lists tickets for a project using either its name or key."""
        try:
            # If no key is provided, try to find it from the project name
            if not project_key and project_name:
                project_key = self._get_key_from_name(project_name)
                if not project_key:
                    return {"result": f"Could not find a Jira project named '{project_name}'."}
            
            if not project_key:
                return {"result": "You must provide a project name or key."}

            issues = self.jira.search_issues(f'project="{project_key}"')
            if not issues:
                return {"result": f"No tickets found in project {project_key}."}

            ticket_list = "\n".join([
                f"- {issue.key}: {issue.fields.summary}" for issue in issues
            ])
            return {"result": f"Tickets in project {project_key}:\n{ticket_list}"}
        except Exception as e:
            return {"result": f"Could not list tickets: {e}", "error": str(e)}


    def create_project(self, project_name: str, project_key: str) -> str:
        try:
            url = f"{self.base_url}/rest/api/3/project"

            payload = {
              "key": project_key,
              "name": project_name,
              "projectTypeKey": "software",
              "projectTemplateKey": "com.pyxis.greenhopper.jira:gh-simplified-scrum-classic",
              "leadAccountId": self.jira.myself()["accountId"]
            }

            response = self.jira._session.post(url, json=payload, headers=self.headers)
            
            print(f"[DEBUG] Status Code: {response.status_code}")
            print(f"[DEBUG] Response Text: {response.text}")
            print(f"[DEBUG] Response Headers: {response.headers}")
            if response.status_code == 201:
               return f"Awesome! The project '{project_name}' with the key '{project_key}' has been created successfully.\n\n🔗 [View on Jira](https://sshivam22singh.atlassian.net/jira/projects/)"
            else:
               return f"[JiraAgent Error] Failed to create project: {response.status_code} {response.text}"

        except Exception as e:
            return f"[JiraAgent Error] Failed to create project: {str(e)}"

        
    def create_ticket(self, project_key: str, title: str, description: str = "", issue_type: str = "Task") -> dict:
        try:
          issue_dict = {
            'project': {'key': project_key},
            'summary': title,
            'description': description or "Created via multi-agent system",
            'issuetype': {'name': issue_type}
          }
          issue = self.jira.create_issue(fields=issue_dict)
          jira_domain = os.getenv("JIRA_DOMAIN", "sshivam22singh.atlassian.net")
          ticket_url = f"https://{jira_domain}/browse/{issue.key}"
          return {
            "result": f"The ticket '{issue.key}' has been successfully created in the project '{project_key}' as a {issue_type}.\n\n🔗 [View Ticket]({ticket_url})",
            "key": issue.key,
            "link": ticket_url
          }
        except Exception as e:
          return {
            "error": f"[JiraAgent Error] Failed to create ticket: {e}"
        }


    def get_ticket(self, key: str = None, project_name: str = None, project_key: str = None) -> dict:
        """
        Retrieves ticket details by key, or lists tickets for a project name if key is not given.
        """
        try:
            if not key:
                # Resolve project_key if not given but project_name is
                if not project_key and project_name:
                    project_key = self._get_key_from_name(project_name)
                    if not project_key:
                        return {"result": f" Could not find a project with name '{project_name}'."}

                if not project_key:
                    return {"result": " Please provide a project key or name to look up tickets."}

                # List all tickets in the project
                jql = f"project = {project_key} ORDER BY created DESC"
                search_url = f"{self.base_url}/rest/api/3/search?jql={jql}"
                search_response = requests.get(search_url, headers=self.headers)
                search_response.raise_for_status()

                tickets = search_response.json().get('issues', [])
                if not tickets:
                    return {"result": f" No tickets found in project '{project_key}'."}

                ticket_list = "\n".join([
                    f"- {t['key']}: {t['fields']['summary']}" for t in tickets
                ])
                return {
                    "result": f" Tickets in project '{project_key}':\n{ticket_list}"
                }

            # If key is provided, get specific ticket
            issue_url = f"{self.base_url}/rest/api/3/issue/{key}"
            issue_response = requests.get(issue_url, headers=self.headers)
            issue_response.raise_for_status()

            ticket_data = issue_response.json()
            fields = ticket_data.get('fields', {})
            summary = fields.get('summary', 'N/A')
            reporter = fields.get('reporter', {}).get('displayName', 'N/A')
            status = fields.get('status', {}).get('name', 'N/A')
            assignee_data = fields.get('assignee')
            assignee = assignee_data.get('displayName', 'Unassigned') if assignee_data else 'Unassigned'

            formatted_details = (
                f" Ticket Details for {key}\n"
                f"- Summary: {summary}\n"
                f"- Status: {status}\n"
                f"- Reporter: {reporter}\n"
                f"- Assignee: {assignee}"
            )
            return {"result": formatted_details}

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return {"result": f" Error: Ticket '{key}' not found."}
            return {"result": f" HTTP error occurred: {e}", "error": str(e)}
        except Exception as e:
            return {"result": f" Failed to retrieve ticket: {e}", "error": str(e)}


    def show_capabilities(self) -> dict:
        """Dynamically lists the capabilities of this agent from its public methods."""
        capabilities = {}
        for name, method in inspect.getmembers(self, inspect.ismethod):
            if not name.startswith('_') and name not in ['show_capabilities', 'normalize_params', 'validate_params', 'run']:
                doc = inspect.getdoc(method)
                description = doc.split('\n')[0] if doc else "No description available."
                capabilities[name] = description
        return {
            "result": "I can manage Jira projects and tickets, including creation and listing.",
            "capabilities": capabilities 
        }