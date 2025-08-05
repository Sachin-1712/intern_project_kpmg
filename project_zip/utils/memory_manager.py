from collections import deque
import json

class MemoryManager:
    """
    Manages both short-term (STM) and long-term (LTM) memory for the AI system.
    """
    def __init__(self, stm_max_len: int = 20):
        """
        Initializes the MemoryManager.
        
        Args:
            stm_max_len (int): The maximum number of messages (user + assistant) to keep in short-term memory.
        """
        
        self.short_term_memory = {}
        
        
        self.long_term_memory = {}

        self.stm_max_len = stm_max_len
        print(f"[INFO] MemoryManager initialized. STM will hold the last {stm_max_len // 2} interactions.")

    

    def add_to_short_term(self, uid: str, user_input: str, assistant_response: str):
        """
        Adds a user-assistant interaction to the short-term memory for a specific user.
        """
        
        if uid not in self.short_term_memory:
            self.short_term_memory[uid] = deque(maxlen=self.stm_max_len)
        
        
        self.short_term_memory[uid].append({"role": "user", "content": user_input})
        self.short_term_memory[uid].append({"role": "assistant", "content": assistant_response})
        print(f"[DEBUG] Added interaction to STM for UID {uid}. Current STM size: {len(self.short_term_memory[uid])} messages.")

    def get_short_term_history(self, uid: str) -> list[dict]:
        """
        Retrieves the short-term memory history for a user.
        """
        return list(self.short_term_memory.get(uid, []))

    

    def add_to_long_term(self, uid: str, data: dict):
        """
        Adds or updates key-value pairs in the long-term memory for a specific user.
        """
        if uid not in self.long_term_memory:
            self.long_term_memory[uid] = {}
        
        self.long_term_memory[uid].update(data)
        print(f"[DEBUG] Updated LTM for UID {uid} with: {data}")

    def get_from_long_term(self, uid: str, key: str) -> any:
        """
        Retrieves a specific value from a user's long-term memory.
        """
        return self.long_term_memory.get(uid, {}).get(key, None)

    def get_all_long_term(self, uid: str) -> dict:
        """
        Retrieves the entire long-term memory for a user.
        """
        return self.long_term_memory.get(uid, {})

    def remember_fact(self, uid: str, fact: str):
        """
        Adds an explicit fact to a special 'user_memos' list in long-term memory.
        """
        if uid not in self.long_term_memory:
            self.long_term_memory[uid] = {}
        
        
        if 'user_memos' not in self.long_term_memory[uid]:
            self.long_term_memory[uid]['user_memos'] = []
            
        self.long_term_memory[uid]['user_memos'].append(fact)
        print(f"[INFO] Explicitly remembered fact for UID {uid}: '{fact}'")