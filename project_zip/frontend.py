import streamlit as st
from master_router import MasterRouter
import json
import uuid

# --- Page Configuration ---
st.set_page_config(
    page_title="Multi Agent Assistant",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="auto",
)

# --- App Title ---
st.title("Multi Agent AI Assistant")

# --- Session State Initialization ---
if 'bot' not in st.session_state:
    st.session_state.bot = MasterRouter()
    st.session_state.uid = str(uuid.uuid4()) 
    st.session_state.messages = [{"role": "assistant", "content": "Hello! How can I assist you today?"}]
    
    st.session_state.show_editor_dialog = False
    st.session_state.edit_saved = None
    st.session_state.code_to_edit = ""
    st.session_state.file_to_edit_path = ""
    st.session_state.repo_to_edit = ""
    st.session_state.sha_to_edit = ""

# --- Helper Function for the Dialog ---
def show_editor_dialog():
    @st.dialog("Interactive File Editor")
    def editor():
        st.write(f"Editing: `{st.session_state.file_to_edit_path}`")
        
        edited_code = st.text_area(
            label="Code Editor", 
            value=st.session_state.code_to_edit, 
            height=500,
            key="editor_text_area"
        )

        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("Save and Push Changes"):
                st.session_state.edited_code = edited_code
                st.session_state.edit_saved = True
                st.rerun()
        with col2:
            if st.button("Cancel"):
                st.session_state.edit_saved = False
                st.rerun()
            
    editor()

# --- Main Application Logic ---

if st.session_state.get("show_editor_dialog", False):
    st.session_state.show_editor_dialog = False
    show_editor_dialog()

elif st.session_state.get("edit_saved") is True:
    st.info("Saving changes and pushing to GitHub...")
    
    git_agent = st.session_state.bot.mcp_servers.get('github')
    
    if git_agent:
        result = git_agent.push_file(
            repo_name=st.session_state.repo_to_edit,
            file_path=st.session_state.file_to_edit_path,
            content=st.session_state.edited_code,
            commit_message="feat: Update file via Streamlit interactive session",
            sha=st.session_state.sha_to_edit
        )

        if result.get("error"):
            st.error(f"Failed to push changes: {result['error']}")
        else:
            st.success(f"Successfully pushed changes to `{st.session_state.file_to_edit_path}`!")
            st.write(f"View changes: {result.get('link')}")
    else:
        st.error("The GitHub agent is not available. Could not push file.")

    for key in ["edit_saved", "edited_code", "code_to_edit", "file_to_edit_path", "repo_to_edit", "sha_to_edit"]:
        if key in st.session_state:
            del st.session_state[key]
    
    st.rerun()

else:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("What can I help you with?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response_summary = st.session_state.bot.process(st.session_state.uid, prompt)
                
                # --- MODIFIED: Logic to conditionally show code ---
                content_to_display = response_summary
                ltm = st.session_state.bot.memory_manager.get_all_long_term(st.session_state.uid)
                
                # Only show code if the user asked to "generate" it and code exists in memory
                if 'generate' in prompt.lower() and 'code' in ltm and ltm['code']:
                    code_block = f"```python\n{ltm['code']}\n```"
                    content_to_display = code_block
                # --- END OF MODIFICATION ---
                
                if not st.session_state.get("show_editor_dialog", False):
                    st.markdown(content_to_display)
                    st.session_state.messages.append({"role": "assistant", "content": content_to_display})
        
        if st.session_state.get("show_editor_dialog", False):
            st.rerun()

# --- Sidebar for Debug Tools ---
with st.sidebar:
    st.header("🛠 Debug Tools")
    st.info("These tools inspect the live state of the backend.")

    if st.button("Show Memory"):
        st.subheader("Stored Memory")
        ltm = st.session_state.bot.memory_manager.get_all_long_term(st.session_state.uid)
        
        if not ltm:
            st.info("Memory is empty.")
        else:
            for key, value in ltm.items():
                if key == 'code':
                    st.write(f"**Code:** `[Code content is stored]`")
                elif isinstance(value, dict):
                    st.write(f"**{key.replace('_', ' ').title()}:**")
                    st.json(value)
                else:
                    st.write(f"**{key.replace('_', ' ').title()}:** `{value}`")

    if st.button("Show Pending Command"):
        pending = st.session_state.bot.last_incomplete_command.get(st.session_state.uid, {})
        st.json(pending if pending else {"pending": "none"})

    if st.button("Clear Conversation"):
        st.session_state.messages = [{"role": "assistant", "content": "Hello! How can I assist you today?"}]
        st.rerun()