
import inspect

class BaseAgentLogic:
    def normalize_params(self, action, params, raw_input=None):
        """
        Generic fallback normalization based on method signature.
        Returns: (params, action, missing_fields_list)
        """
        needs = []
        method = getattr(self, action, None)

        if callable(method):
            sig = inspect.signature(method)
            for param in sig.parameters.values():
                if param.default == inspect.Parameter.empty and param.name not in params:
                    needs.append(param.name)
        return params, action, needs
