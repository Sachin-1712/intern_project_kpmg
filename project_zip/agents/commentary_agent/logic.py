from utils.llm_wrapper import CrewCompatibleLLM

class CommentaryAgentLogic:
    def __init__(self):
        self.llm = CrewCompatibleLLM()
        self.prompt_template = self.llm.load_prompt("commentary")

    def beautify(self, user_input: str, raw_result: str, link: str = None) -> str:
        """
        Takes raw agent output and beautifies it for the end-user.
        """
        prompt = self.prompt_template.replace("<USER_INPUT>", user_input) \
                                      .replace("<RAW_RESULT>", raw_result) \
                                      .replace("<LINK>", link if link else "N/A")
        try:
            beautified_response = self.llm.call([{"role": "user", "content": prompt}])
            return beautified_response
        except Exception as e:
            print(f"[ERROR][CommentaryAgent] Failed to beautify output: {e}")
            # Fallback to the raw result if beautification fails
            return raw_result