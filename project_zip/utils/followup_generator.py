import os
from utils.llm_wrapper import CrewCompatibleLLM

class FollowUpGenerator:
    def __init__(self):
        self.llm = CrewCompatibleLLM()
        self.prompt_path = os.path.join("prompts", "followup.prompt")

    def generate_followup(self, user_input: str, assistant_response: str) -> str:
        try:
            with open(self.prompt_path, "r") as f:
                template = f.read()

            context_text = "\n".join([
                f"User: {user_input}",
                f"Assistant: {assistant_response}"
            ])
            prompt = template.replace("<CONTEXT>", context_text)

            response = self.llm.call([{"role": "system", "content": prompt}])
            return response.strip()

        except Exception as e:
            print(f"[ERROR] Failed to generate follow-up: {e}")
            return ""
