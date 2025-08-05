import os
import json
import pandas as pd
import requests
from crewai import Agent
import inspect

class DataAgentLogic:
    def __init__(self):
        self.github_token = os.getenv("GITHUB_PAT")
        self.headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github+json"
        }

        self.agent = Agent(
            role="Data Analyst & Preprocessor",
            goal="Help users with tasks related to data exploration, conversion, and GitHub project analysis.",
            backstory=(
                "You are a skilled data operations agent with strong knowledge of data cleaning, analysis, and conversion. "
                "You can analyze CSVs, validate JSON, and find useful projects from GitHub to assist developers in their data workflows. "
                "You’re precise, efficient, and user-friendly."
            ),
            allow_delegation=False,
            verbose=True
        )

    def search_github_projects(self, query: str):
        url = f"https://api.github.com/search/repositories?q={query}"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            items = response.json().get("items", [])[:5]
            return "\n".join([f" [{item['full_name']}]({item['html_url']})" for item in items])
        return " GitHub search failed."

    def validate_json(self, data: str):
        try:
            json.loads(data)
            return " JSON is valid."
        except json.JSONDecodeError:
            return " Invalid JSON."

    def perform_eda(self, file_path: str):
        try:
            df = pd.read_csv(file_path)
            info = df.describe(include='all').to_string()
            return f" Summary Stats for {file_path}:\n{info[:1500]}..."
        except Exception as e:
            return f" Failed EDA on {file_path}: {e}"

    def convert_csv_to_json(self, file_path: str):
        try:
            df = pd.read_csv(file_path)
            json_data = df.to_json(orient="records", indent=2)
            json_path = file_path.replace(".csv", ".json")
            with open(json_path, "w") as f:
                f.write(json_data)
            return f" Converted {file_path} to {json_path}."
        except Exception as e:
            return f" CSV to JSON failed: {e}"

    def convert_json_to_csv(self, file_path: str):
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
            df = pd.DataFrame(data)
            csv_path = file_path.replace(".json", ".csv")
            df.to_csv(csv_path, index=False)
            return f" Converted {file_path} to {csv_path}."
        except Exception as e:
            return f" JSON to CSV failed: {e}"

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
            "result": "I can search for data and projects across github.",
            "capabilities": capabilities 
        }
