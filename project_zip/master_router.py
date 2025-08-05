import json
import re
import os
import inspect
import importlib
from dotenv import load_dotenv

from utils.llm_wrapper import CrewCompatibleLLM
from utils.prompt_helper import get_missing_param_prompt_from_llm
from utils.interpreter import extract_intent_and_args
from utils.followup_generator import FollowUpGenerator 
from utils.memory_manager import MemoryManager

class MasterRouter:
    """
    An intelligent, stateful router that processes user input, determines intent,
    and delegates tasks to specialized agents based on a configuration file.
    """
    def __init__(self, config_path: str = 'config.json'):
        self.memory_manager = MemoryManager()
        load_dotenv()
        self.llm = CrewCompatibleLLM()
        # Inside MasterRouter __init__ method
        self.followup_gen = FollowUpGenerator()
        
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.prompts = self.config['prompts']
        self.flags = self.config['flags']
        self.messages = self.config['messages']
        self.chat_actions = self.config['chat_actions']

        
        self.mcp_servers = self._load_agents_from_config()
        self.commentary_agent = self._load_agent("agents.commentary_agent.logic", "CommentaryAgentLogic")()

        self.last_incomplete_command = {}
        self.followup_display_prefix = os.getenv("FOLLOWUP_DISPLAY_PREFIX", self.config['display']['followup_prefix'])

    def _load_agent(self, module_path: str, class_name: str):
        """Helper to dynamically import a module and return a class object."""
        module = importlib.import_module(module_path)
        return getattr(module, class_name)

    def _load_agents_from_config(self) -> dict:
        """Dynamically load all agents specified in the config file."""
        agents = {}
        for agent_name, agent_config in self.config['agents'].items():
            try:
                AgentClass = self._load_agent(agent_config['module'], agent_config['class'])
                agents[agent_name] = AgentClass()
                print(f"[INFO] Successfully loaded agent: {agent_name}")
            except Exception as e:
                print(f"[ERROR] Failed to load agent {agent_name}: {e}")
        return agents

 
    def process(self, uid: str, user_input: str) -> str:
        """Main entry point for processing all user input."""
        print(f"\n[DEBUG] Current LTM for UID {uid}: {json.dumps(self.memory_manager.get_all_long_term(uid), indent=2)}")
        print(f"[DEBUG] Last incomplete command for UID {uid}: {json.dumps(self.last_incomplete_command.get(uid, {}), indent=2)}")
        
        try:
            stm_history = self.memory_manager.get_short_term_history(uid)
            
            current_parsed = extract_intent_and_args(user_input, self.last_incomplete_command.get(uid), short_term_memory=stm_history)
            current_parsed["raw_input"] = user_input
            print(f"[DEBUG] After extract_intent_and_args, current_parsed: {json.dumps(current_parsed, indent=2)}")
        except Exception as e:
            print(f"[ERROR] Initial intent parsing failed for '{user_input}': {e}")
            
            if uid in self.last_incomplete_command:
                return self._reprompt_for_missing_params(self.last_incomplete_command[uid])
            return self._llm_response("unclear_command")

        # --- START: CORRECTED LOGIC ---
        # Try to fulfill needs from memory BEFORE deciding the command is incomplete
        ltm = self.memory_manager.get_all_long_term(uid)
        if 'content' in current_parsed.get('needs', []) and 'code' in ltm:
            current_parsed['params']['content'] = ltm['code']
            print(f"[INFO] Automatically filled 'content' parameter from memory.")
            # Remove 'content' from needs since it's now fulfilled
            current_parsed['needs'].remove('content')
        # --- END: CORRECTED LOGIC ---

        if uid in self.last_incomplete_command:
            return self._handle_incomplete_command(uid, current_parsed)

        if not current_parsed.get("needs"):
            return self._route(current_parsed, uid)
        
        if current_parsed.get("needs"):
            self.last_incomplete_command[uid] = current_parsed
            return self._reprompt_for_missing_params(current_parsed)
        
        return self._llm_response("unclear_command")

    # In master_router.py

    def _handle_incomplete_command(self, uid: str, current_parsed: dict) -> str:
        """Handles logic when the system is waiting for parameters for a previous command."""
        # Get the original command that was missing info
        previous_ctx = self.last_incomplete_command[uid]
        original_needs = previous_ctx.get("needs", [])

        # Update the original command's parameters with the new info the user just provided
        previous_ctx["params"].update(current_parsed.get("params", {}))

        # --- ✨ NEW ROBUST LOGIC ✨ ---
        # After updating, recalculate what is STILL missing
        remaining_needs = [field for field in original_needs if field not in previous_ctx["params"]]

        # If nothing is missing, the command is finally complete and can be executed
        if not remaining_needs:
            print("[INFO] All parameters fulfilled. Routing command.")
            del self.last_incomplete_command[uid]
            return self._route(previous_ctx, uid)
        else:
            # If parameters are still missing, update the context and ask for the next one
            print(f"[INFO] Parameters still missing: {remaining_needs}")
            previous_ctx["needs"] = remaining_needs
            self.last_incomplete_command[uid] = previous_ctx
            return self._reprompt_for_missing_params(previous_ctx)

    def _reprompt_for_missing_params(self, command_context: dict) -> str:
        """Generates the user-facing prompt for needed parameters."""
        missing_params_display = [m.replace('_', ' ') for m in command_context.get("needs", [])]
        prompt_template = self.prompts['router_responses']['missing_params']
        return prompt_template.format(needs=', '.join(missing_params_display))
    
    def remember_this(self, uid: str, fact: str, raw_input: str) -> dict:
        """Handles the 'remember_this' action."""
        print(f"[INFO][MasterRouter] Remembering fact for UID {uid}: '{fact}'")
        self.memory_manager.remember_fact(uid, fact)
        result = self.messages['remember_success'].format(fact=fact)
        self.memory_manager.add_to_short_term(uid, raw_input, result)
        return {"result": result}

    def query_memory(self, uid: str, query: str, raw_input: str) -> dict:
        """Handles the 'query_memory' action."""
        print(f"[INFO][MasterRouter] Querying LTM for UID {uid} with query: '{query}'")
        response = self._handle_memory_query(uid, query)
        result = response if response else self.messages['memory_query_fail']
        self.memory_manager.add_to_short_term(uid, raw_input, result)
        return {"result": result}

    def get_chat_history(self, uid: str, raw_input: str) -> dict:
        """Handles the 'get_chat_history' action."""
        print(f"[INFO][MasterRouter] Retrieving chat history for UID {uid}")
        stm_history = self.memory_manager.get_short_term_history(uid)
        if not stm_history:
            result = self.messages['no_history']
        else:
            formatted_history = "\n".join([f"- {msg['role'].capitalize()}: {msg['content']}" for msg in stm_history])
            result = self.messages['history_header'].format(formatted_history=formatted_history)
        self.memory_manager.add_to_short_term(uid, raw_input, result)
        return {"result": result}

    def _handle_memory_query(self, uid: str, query: str) -> str:
        """Uses an LLM to answer a question based on stored long-term memory."""
        user_ltm = self.memory_manager.get_all_long_term(uid)
        if not user_ltm: return ""
        all_facts = [f"{k.replace('_', ' ')} is {v}" for k, v in user_ltm.items()]
        if 'user_memos' in user_ltm and user_ltm['user_memos']:
            all_facts.extend(user_ltm['user_memos'])
        if not all_facts: return ""
        facts_str = "\n- ".join(map(str, all_facts))
        llm_prompt = self.prompts['memory_query'].format(query=query, facts_str=facts_str)
        try:
            response = self.llm.call([{"role": "user", "content": llm_prompt}], temperature=0.0).strip()
            return "" if response.upper() == self.flags['none'] else self._llm_response("memory_value_found", variables={"value": response})
        except Exception as e:
            print(f"[ERROR] LLM memory search failed: {e}")
            return ""

    def _route(self, parsed: dict, uid: str) -> str:
        """The final routing, validation, and execution logic."""
        agent_name = parsed.get("agent")
        action = parsed.get("action")
        params = parsed.get("params", {})
        raw_input = parsed.get("raw_input", "")

        # Handle special 'chat' agent actions first
        if agent_name == self.flags['chat_agent_name']:
            if action == self.chat_actions['remember']:
                return self.remember_this(uid, params.get("fact", raw_input), raw_input).get("result")
            if action == self.chat_actions['query_memory']:
                return self.query_memory(uid, params.get("query", raw_input), raw_input).get("result")
            if action == self.chat_actions['get_history']:
                return self.get_chat_history(uid, raw_input).get("result")
            if action == self.chat_actions['show_capabilities']:
                return self._get_all_agents_capabilities()
            else: 
                chat_agent = self.mcp_servers.get(self.flags['chat_agent_name'])
                agent_response = chat_agent.run(raw_input, parsed)
                raw_result = agent_response.get("result", self.messages['action_complete'])
                beautified_response = self.commentary_agent.beautify(raw_input, raw_result)
                return beautified_response if beautified_response else raw_result

        handler = self.mcp_servers.get(agent_name)
        if not handler:
            return self.prompts['router_responses']['unsupported_agent'].format(agent=agent_name)

        # You can add the validation logic back in here if you need it
        # if hasattr(handler, "validate_params") and callable(getattr(handler, "validate_params")):
        #     ...

        method_to_call = getattr(handler, action, None)
        if not (method_to_call and callable(method_to_call)):
            return self.prompts['router_responses']['unsupported_action'].format(agent=agent_name, action=action)

        try:
            sig = inspect.signature(method_to_call)
            filtered_params = {k: v for k, v in params.items() if k in sig.parameters}
            result_obj = method_to_call(**filtered_params)
        except Exception as e:
            return self.prompts['router_responses']['execution_error'].format(agent=agent_name, action=action, error=str(e))

        if not isinstance(result_obj, dict):
            result_obj = {"result": str(result_obj)}

        # --- ✨ MODIFIED LOGIC TO DISPLAY FILE CONTENT ✨ ---
        raw_result_text = result_obj.get("result", self.messages['action_complete'])
        
        # If the action was getting file content, append the content to the result
        if action == "get_file_content" and "content" in result_obj:
            file_path = params.get('file_path', 'the file')
            code_content = result_obj.get("content", "")
            # Append the formatted code to the result message
            raw_result_text += f"\n\nHere is the content of `{file_path}`:\n\n```python\n{code_content}\n```"
        # --- END MODIFIED LOGIC ---

        self._infer_and_store_memory(uid, agent_name, action, params, result_obj)
        self.memory_manager.add_to_short_term(uid, raw_input, raw_result_text)
        
        final_response = self.commentary_agent.beautify(raw_input, raw_result_text, result_obj.get("link"))
        
        if not final_response or not final_response.strip():
            final_response = raw_result_text
            
        followup = self.followup_gen.generate_followup(raw_input, raw_result_text)
        if followup and followup.upper() != self.flags['none']:
            final_response += f"\n\n{self.followup_display_prefix}{followup}"
            
        return final_response.strip()
    
    def _get_all_agents_capabilities(self) -> str:
        """Generates a summary of all agent capabilities using their docstrings."""
        all_capabilities_list = []
        for agent_name, agent_instance in self.mcp_servers.items():
            if hasattr(agent_instance, "show_capabilities"):
                try:
                    cap_info = agent_instance.show_capabilities()
                    if isinstance(cap_info, dict):
                        # Get the agent's high-level description
                        agent_desc = cap_info.get("result", "")
                        
                        # Get the dictionary of capabilities
                        capabilities_dict = cap_info.get("capabilities", {})
                        
                        # Format the capabilities for display
                        if capabilities_dict:
                            caps_str_list = [f"\n    - `{name}`: {desc}" for name, desc in capabilities_dict.items()]
                            caps_str = "".join(caps_str_list)
                            all_capabilities_list.append(f"- **{agent_name.capitalize()}**: {agent_desc}{caps_str}")
                        else:
                            all_capabilities_list.append(f"- **{agent_name.capitalize()}**: {agent_desc}")

                except Exception as e:
                    print(f"[ERROR] Could not get capabilities for {agent_name}: {e}")
        
        capabilities_text = "\n".join(all_capabilities_list)
        return self._llm_response("all_capabilities_list", variables={"capabilities_list": capabilities_text})

    def _infer_and_store_memory(self, uid: str, agent: str, action: str, params: dict, result_obj: dict):
        """Uses an LLM to decide what to save to long-term memory after an action."""
        inferred_memory = {}

        # --- START: Added Code ---
        # Add a specific, hard-coded rule to always save generated code.
        if agent == 'developer' and action == 'generate_code' and 'result' in result_obj:
            print("[INFO] Applying hard-coded rule to store generated code.")
            inferred_memory = {'code': result_obj['result']}
        # --- END: Added Code ---
        
        else:
            # Fallback to LLM inference for all other cases
            template = self.prompts['memory_storage_inference']
            content = template.replace("<AGENT>", agent) \
                                    .replace("<ACTION>", action) \
                                    .replace("<PARAMS_JSON>", json.dumps(params)) \
                                    .replace("<RESULT_OBJ_JSON>", json.dumps(result_obj))
            try:
                response_format = {"type": "json_object"} if self.llm.llm_provider == self.flags['openai_provider'] else None
                json_str = self.llm.call([{"role": "user", "content": content}], temperature=0.0, response_format=response_format).strip()
                if json_str and json_str != '{}':
                    inferred_memory = json.loads(json_str)
            except Exception as e:
                print(f"[ERROR] LLM memory storage inference failed for {agent}.{action}: {e}")
                return # Exit if inference fails

        if isinstance(inferred_memory, dict) and inferred_memory:
            self.memory_manager.add_to_long_term(uid, inferred_memory)
            print(f"[INFO] Stored LLM-inferred memory for UID {uid}: {inferred_memory}")

    def _llm_response(self, intent_type: str, variables: dict = None) -> str:
        """Formats and calls the LLM for predefined router responses."""
        template = self.prompts['router_responses'].get(intent_type, self.messages['error_fallback'])
        if variables:
            for key, value in variables.items():
                template = template.replace(f"{{{key}}}", str(value))
        try:
            
            return self.llm.call([{"role": "user", "content": template}])
        except Exception as e:
            print(f"[ERROR] Failed LLM response generation for intent_type '{intent_type}': {e}")
            return self.messages['error_fallback']