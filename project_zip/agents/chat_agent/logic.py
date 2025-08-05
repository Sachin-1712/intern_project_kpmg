from crewai import Agent
from utils.llm_wrapper import CrewCompatibleLLM
from base_agent_logic import BaseAgentLogic  


class ChatAgentLogic(BaseAgentLogic):
    """General-purpose conversational LLM (Q&A, chit-chat)."""

    def __init__(self):
        self.llm = CrewCompatibleLLM()
        self.agent = Agent(
            role="Helpful AI Assistant",
            goal="Answer user questions clearly and concisely.",
            backstory="Knows general world knowledge up to its training cutoff.",
            llm=self.llm,
            memory=False
        )

    def run(self, user_query: str, parsed_input: dict) -> dict:
        print(f"[INFO] ChatAgent received query: {user_query}")
        try:
            system_prompt = "You are a helpful assistant. Answer the user's question directly and concisely."
            llm_response_content = self.llm.call([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ])
            return {"result": llm_response_content}
        except Exception as e:
            print(f"[ChatAgent Error] Failed: {e}")
            return {"result": f"Sorry, I encountered an error: {e}"}

    def process_unsupported(self, raw_input: str) -> dict:
        return self.run(raw_input, {
            "agent": "chat",
            "action": "chat",
            "params": {},
            "raw_input": raw_input
        })

    def show_capabilities(self) -> dict:
        return {
            "result": "I can engage in general conversation, answer factual questions, and provide helpful information.",
            "capabilities": [
                "chat",
                "answer_questions",
                "provide_info",
                "general_assistance"
            ]
        }
    
    
