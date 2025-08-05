import json
from utils.llm_wrapper import CrewCompatibleLLM

def load_prompt_template(path: str) -> str:
    with open(path, "r") as f:
        return f.read()

def get_missing_param_prompt_from_llm(agent, action, needs, provided_params, raw_input):
    template = load_prompt_template("prompts/missing_params_prompt.prompt")
    prompt = template \
        .replace("{{action}}", action) \
        .replace("{{agent}}", agent) \
        .replace("{{raw_input}}", raw_input) \
        .replace("{{provided_params}}", json.dumps(provided_params, indent=2)) \
        .replace("{{needs}}", json.dumps(needs, indent=2))
    
    return CrewCompatibleLLM().complete(prompt).strip()
