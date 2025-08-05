import json
from utils.llm_wrapper import CrewCompatibleLLM

_llm = CrewCompatibleLLM()

def extract_intent_and_args(message: str, incomplete_command_context: dict = None, short_term_memory: list = None) -> dict:
    """
    Extracts agent, action, and parameters from user input, using context from
    incomplete commands and short-term memory.
    """
    try:
        
        interpreter_prompt_content = _llm.load_prompt("interpreter")
        system_prompt_parts = [interpreter_prompt_content]

        
        if short_term_memory:
            history_str = "\n".join([f"- {msg['role']}: {msg['content']}" for msg in short_term_memory])
            system_prompt_parts.append(
                f"\n**Recent Conversation History (for context):**\n{history_str}\n"
            )

        
        if incomplete_command_context:
            system_prompt_parts.append(
                f"\n**Active Incomplete Command Context:**\n```json\n{json.dumps(incomplete_command_context, indent=2)}\n```\n\n"
                "**Crucial Instruction for THIS turn:** Based on the `Active Incomplete Command Context` above,"
                " if the current `User` input seems to provide a value for one of the `needs` in that context,"
                " **do NOT change the `agent` or `action`**. Instead, fill the corresponding `param` and update the `needs` list accordingly."
                " Only if the current `User` input is clearly a new, distinct command, should you infer a new agent/action."
            )
        
        final_system_prompt = "\n".join(system_prompt_parts)

        messages = [
            {"role": "system", "content": final_system_prompt},
            {"role": "user", "content": message},
        ]

        
        response_format_arg = {"type": "json_object"} if _llm.llm_provider in ["openai", "azure_openai"] else None
        raw_llm_response = _llm.call(
            messages,
            temperature=0.0,
            response_format=response_format_arg
        )

       
        processed_response_str = raw_llm_response.strip()
        if processed_response_str.startswith("```json"):
            processed_response_str = processed_response_str[len("```json"):].strip()
        if processed_response_str.endswith("```"):
            processed_response_str = processed_response_str[:-len("```")].strip()
        
        if not processed_response_str:
            return {"agent": "unknown", "action": "unknown", "params": {}, "needs": [], "raw_input": message}

        parsed_intent = json.loads(processed_response_str)

        if not isinstance(parsed_intent, dict):
            raise ValueError("LLM response is not a dictionary (invalid JSON structure).")
        
        parsed_intent.setdefault("agent", "unknown")
        parsed_intent.setdefault("action", "unknown")
        parsed_intent.setdefault("params", {})
        parsed_intent.setdefault("needs", [])
        parsed_intent["raw_input"] = message

        if not isinstance(parsed_intent["agent"], str): parsed_intent["agent"] = "unknown"
        if not isinstance(parsed_intent["action"], str): parsed_intent["action"] = "unknown"
        if not isinstance(parsed_intent["params"], dict): parsed_intent["params"] = {}
        if not isinstance(parsed_intent["needs"], list): parsed_intent["needs"] = []

        return parsed_intent

    except json.JSONDecodeError as e:
        print(f"[ERROR] Interpreter JSONDecodeError: {e}. Raw response: '{raw_llm_response}'")
        return {"agent": "unknown", "action": "unknown", "params": {}, "needs": [], "raw_input": message}
    except Exception as e:
        print(f"[ERROR] Interpreter Exception: {e}")
        return {"agent": "unknown", "action": "unknown", "params": {}, "needs": [], "raw_input": message}