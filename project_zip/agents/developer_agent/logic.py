import json
from crewai import Agent
from utils.llm_wrapper import CrewCompatibleLLM
from base_agent_logic import BaseAgentLogic
import inspect

class DeveloperAgentLogic(BaseAgentLogic):
    def __init__(self):
        self.llm = CrewCompatibleLLM()
        self.agent = Agent(
            role="AI Software Developer",
            goal="To assist in generating, debugging, optimizing, and translating high-quality code.",
            backstory=(
                "You are an expert AI software developer agent created to support programmers by generating accurate, "
                "efficient, and understandable code. With deep knowledge across programming languages and software design, "
                "you help teams accelerate their development process by writing clean code, explaining logic, "
                "fixing bugs, and translating across tech stacks."
            ),
            allow_delegation=False,
            verbose=True,
            llm=self.llm
        )

    def generate_code(self, language: str, task: str) -> dict:
        """Generates a clean code block for a given task."""
        if not language or language.lower() == "unknown":
            language = "python"  # Default to Python if not specified

        # This direct prompt ensures code-only output.
        prompt = f"""
You are an expert code generation AI. Your only purpose is to generate a single, clean, and complete code block in {language}.

Do NOT provide any explanations, conversational text, introductions, or apologies.

Generate the code for the following task:
{task}
"""
        try:
            print(f"[DeveloperAgent] Calling LLM with direct code generation prompt...")
            raw_code = self.llm.call([{"role": "user", "content": prompt}]).strip()
            
            clean_code = self._clean_code_from_llm(raw_code, language)
            
            # The main 'result' is now the clean code.
            return {
                "result": clean_code,
                "code": clean_code
            }
        except Exception as e:
            print(f"[ERROR] An error occurred while generating code: {e}")
            return {"result": f"[DeveloperAgent Error] LLM failed: {e}"}

    def _clean_code_from_llm(self, llm_output: str, language: str) -> str:
        """A simple helper to remove markdown formatting from LLM code output."""
        if llm_output.startswith(f"```{language}"):
            llm_output = llm_output[len(f"```{language}"):]
        elif llm_output.startswith("```"):
            llm_output = llm_output[3:]

        if llm_output.endswith("```"):
            llm_output = llm_output[:-3]
        
        return llm_output.strip()

    def explain_code(self, code: str = "") -> dict:
        if not code:
            return {"result": "[DeveloperAgent Error] 'code' parameter is missing for explain_code."}
        prompt = f"Explain this code:\n```python\n{code}\n```"
        return self._call_llm(prompt)

    def optimize_code(self, code: str = "") -> dict:
        if not code:
            return {"result": "[DeveloperAgent Error] 'code' parameter is missing for optimize_code."}
        prompt = f"Optimize this code:\n```python\n{code}\n```"
        return self._call_llm(prompt)

    def fix_bug(self, code: str = "") -> dict:
        if not code:
            return {"result": "[DeveloperAgent Error] 'code' parameter is missing for fix_bug."}
        prompt = f"Fix bugs in this code:\n```python\n{code}\n```"
        return self._call_llm(prompt)

    def convert_code(self, code: str = "", from_language: str = "", to_language: str = "", target_language: str = "") -> dict:
        if not code:
            return {"result": "[DeveloperAgent Error] 'code' parameter is missing for translate_code."}
        final_target = to_language or target_language
        if not final_target:
            return {"result": "[DeveloperAgent Error] Missing target language for translation."}

        prompt = f"Translate this code from {from_language} to {final_target}:\n```{from_language or 'text'}\n{code}\n```"
        return self._call_llm(prompt)

    def _call_llm(self, prompt: str, extra=None) -> dict:
        try:
            print(f"[DeveloperAgent] Calling LLM with prompt: {prompt[:100]}...")
            result = self.llm.call([{"role": "user", "content": prompt}])
            return {"result": result, **(extra or {})}
        except Exception as e:
            print(f"[DeveloperAgent Error] LLM call failed: {e}")
            return {"result": f"[DeveloperAgent Error] LLM call failed: {e}"}

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
            "result": "I can generate, explain, optimize, and translate code in various languages.",
            "capabilities": capabilities 
        }