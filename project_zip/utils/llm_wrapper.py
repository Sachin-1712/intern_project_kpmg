import os
import json
from openai import AzureOpenAI
from dotenv import load_dotenv

class CrewCompatibleLLM:
    def __init__(self):
        load_dotenv()

        self.llm_provider = "azure_openai"

        self.api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION")
        self.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

        missing_vars = []
        if not self.api_key: missing_vars.append("AZURE_OPENAI_API_KEY")
        if not self.api_version: missing_vars.append("AZURE_OPENAI_API_VERSION")
        if not self.azure_endpoint: missing_vars.append("AZURE_OPENAI_ENDPOINT")
        if not self.deployment_name: missing_vars.append("AZURE_OPENAI_DEPLOYMENT_NAME")
        
        if missing_vars:
            error_msg = f"[ERROR LLM Wrapper] Missing environment variables for Azure OpenAI: {', '.join(missing_vars)}."
            raise ValueError(error_msg)

        try:
            self.client = AzureOpenAI(
                api_key=self.api_key,
                api_version=self.api_version,
                azure_endpoint=self.azure_endpoint,
            )
        except Exception as e:
            print(f"[CRITICAL ERROR LLM Wrapper] Failed to initialize Azure OpenAI client: {e}")
            raise

        self.prompts_dir = os.path.join(os.path.dirname(__file__), "../prompts")
        if not os.path.exists(self.prompts_dir):
            raise FileNotFoundError(f"Prompts directory not found at: {self.prompts_dir}")

    def call(self, messages: list, temperature: float = 0.7, max_tokens: int = 1024, response_format: dict = None) -> str:
        """
        Makes a call to the Azure OpenAI LLM API.
        Args:
            messages (list): List of message dictionaries [{role: "user", content: "..."}]
            temperature (float): Controls the randomness of the output.
            max_tokens (int): Maximum number of tokens to generate.
            response_format (dict): Optional. For OpenAI, e.g., {"type": "json_object"}.
        Returns:
            str: The generated text response from the LLM, or an empty string on error/no content.
        """
        try:
            openai_params = {
                "model": self.deployment_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if response_format:
                openai_params["response_format"] = response_format

            resp = self.client.chat.completions.create(**openai_params)
            
            response_text = ""
            if resp.choices and resp.choices[0].message and resp.choices[0].message.content:
                response_text = resp.choices[0].message.content
            else:
                return ""
            
            return response_text.strip()

        except Exception as e:
            print(f"[CRITICAL ERROR LLM Call] An exception occurred during Azure OpenAI API call: {type(e).__name__}: {e}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                print(f"[CRITICAL ERROR LLM Call] API Error Response Text (if available): {e.response.text}")
            elif hasattr(e, 'body'):
                print(f"[CRITICAL ERROR LLM Call] API Error Body (if available): {e.body}")
            return ""

    def load_prompt(self, name: str) -> str:
        file_path_txt = os.path.join(self.prompts_dir, f"{name}.txt")
        file_path_prompt = os.path.join(self.prompts_dir, f"{name}.prompt")

        if os.path.exists(file_path_txt):
            path = file_path_txt
        elif os.path.exists(file_path_prompt):
            path = file_path_prompt
        else:
            raise FileNotFoundError(f"Missing prompt file: {name}. Looked for {name}.txt and {name}.prompt in {self.prompts_dir}")
        
        with open(path, 'r', encoding="utf-8") as f:
            return f.read().strip()