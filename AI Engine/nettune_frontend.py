#!/usr/bin/env python3

import streamlit as st
from typing import List, Tuple, Dict, Any, Optional
import time

# Import backend service
from nettune_backend import get_backend, NetTuneBackend


class NetTuneFrontend:
    """Frontend UI class for NetTune AI Pod Placement Assistant"""
    
    def __init__(self):
        self.backend = get_backend()
    
    def initialize_session_state(self):
        """Initialize Streamlit session state variables"""
        if 'messages' not in st.session_state:
            st.session_state.messages = []
        if 'backend_initialized' not in st.session_state:
            st.session_state.backend_initialized = False
        if 'qa_history' not in st.session_state:
            st.session_state.qa_history = []
        if 'df_result' not in st.session_state:
            st.session_state.df_result = None
        if 'total_tokens' not in st.session_state:
            st.session_state.total_tokens = 0
        if 'initialization_status' not in st.session_state:
            st.session_state.initialization_status = None
    
    def setup_page_config(self):
        """Configure Streamlit page settings"""
        st.set_page_config(
            page_title="Pod Placement AI - Pod Placement Assistant",
            page_icon="🤖",
            layout="wide"
        )
    
    def apply_custom_css(self):
        """Apply custom CSS styling"""
        st.markdown("""
        <style>
        .main-header {
            font-size: 2.5rem;
            font-weight: bold;
            color: #1f77b4;
            text-align: center;
            margin-bottom: 1rem;
        }
        .sub-header {
            font-size: 1.2rem;
            color: #666;
            text-align: center;
            margin-bottom: 2rem;
        }
        .status-info {
            padding: 0.5rem;
            border-radius: 0.5rem;
            margin: 0.5rem 0;
            font-size: 0.9rem;
        }
        .thinking {
            background-color: #e1f5fe;
            border-left: 4px solid #01579b;
            padding: 1rem;
            margin: 1rem 0;
            border-radius: 0.5rem;
        }
        .context-source {
            background-color: #f3e5f5;
            border-left: 4px solid #7b1fa2;
            padding: 0.5rem;
            margin: 0.5rem 0;
            border-radius: 0.5rem;
            font-size: 0.9rem;
        }
        .error-message {
            background-color: #ffebee;
            border-left: 4px solid #f44336;
            padding: 1rem;
            margin: 1rem 0;
            border-radius: 0.5rem;
            color: #c62828;
        }
        .success-message {
            background-color: #e8f5e8;
            border-left: 4px solid #4caf50;
            padding: 1rem;
            margin: 1rem 0;
            border-radius: 0.5rem;
            color: #2e7d32;
        }
        </style>
        """, unsafe_allow_html=True)
    
    def render_header(self):
        """Render the main header"""
        st.markdown('<div class="main-header">🤖 Pod Placement AI Assistant</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-header">Network Pod Placement Assistant</div>', unsafe_allow_html=True)
    
    def initialize_backend(self):
        """Initialize the backend service"""
        if not st.session_state.backend_initialized:
            with st.spinner("🔄 Initializing Pod Placement AI Backend..."):
                tokenizer_path = r"C:\Users\aakash.a1\Documents\VRN\Qwen3-32B"
                
                try:
                    result = self.backend.initialize(tokenizer_path)
                    st.session_state.initialization_status = result
                    
                    if result["status"] == "success":
                        st.session_state.backend_initialized = True
                        st.success("✅ Pod Placement AI backend initialized successfully!")
                        
                        # Display initialization details
                        data_info = result.get("data_loaded", {})
                        st.info(f"📊 Loaded {data_info.get('dimensioning_records', 0)} dimensioning records and {data_info.get('pod_flavor_records', 0)} pod flavor records")
                    else:
                        st.error(f"❌ Backend initialization failed: {result['message']}")
                        st.stop()
                        
                except Exception as e:
                    st.error(f"❌ Failed to initialize backend: {str(e)}")
                    st.stop()
    
    def render_sidebar(self):
        """Render the sidebar with controls and information"""
        with st.sidebar:
            st.header("🔧 Controls")
            
            # New Chat Button
            if st.button("🆕 Start New Chat", use_container_width=True):
                self.start_new_chat()
            
            st.divider()
            
            # Session Info
            st.header("📊 Session Info")
            st.info(f"💬 Messages: {len(st.session_state.messages)}")
            st.info(f"📈 Total Tokens: {st.session_state.total_tokens}")
            
            # Backend Status
            if st.session_state.backend_initialized:
                backend_status = self.backend.get_status()
                st.success("✅ Backend: Online")
                
                with st.expander("🔍 Backend Details"):
                    st.json(backend_status)
            else:
                st.warning("⚠️ Backend: Initializing...")
            
            # Dimensioning Data Status
            if st.session_state.df_result:
                st.success("✅ Dimensioning data loaded")
                with st.expander("🔍 View Parsed Data"):
                    st.json(st.session_state.df_result)
            
            st.divider()
            
            # Sample Queries
            st.header("💡 Sample Queries")
            sample_queries = [
                "What are the dimensioning flavors for uADPF?",
                "Show me pod placement for medium-regular-spr-t21",
                "What are the resources for DPP pod?",
                "Pod placement analysis needed"
            ]
            
            for query in sample_queries:
                if st.button(f"💬 {query}", key=f"sample_{hash(query)}", use_container_width=True):
                    self.process_user_input(query)
            
            st.markdown("---")
            st.markdown("*Click any sample query to try it out!*")
    
    def start_new_chat(self):
        """Start a new chat session"""
        st.session_state.messages = []
        st.session_state.qa_history = []
        st.session_state.df_result = None
        # Reset backend session if needed
        self.backend.reset_session()
        st.rerun()
    
    def render_chat_history(self):
        """Render the chat message history"""
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                if message["role"] == "assistant":
                    if "context_source" in message:
                        st.markdown(f'<div class="context-source">{message["context_source"]}</div>', unsafe_allow_html=True)
                    if "error" in message:
                        st.markdown(f'<div class="error-message">{message["content"]}</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(message["content"])
                else:
                    st.markdown(message["content"])
    
    def process_user_input(self, user_input: str):
        """Process user input and get response from backend"""
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(user_input)
        
        # Process query with backend
        with st.chat_message("assistant"):
            # Show thinking animation
            thinking_placeholder = st.empty()
            with thinking_placeholder.container():
                st.markdown('<div class="thinking">🤔 Pod Placement AI is thinking...</div>', unsafe_allow_html=True)
            
            try:
                # Call backend to process query
                result = self.backend.process_query(
                    user_input, 
                    st.session_state.qa_history, 
                    st.session_state.df_result
                )
                
                # Clear thinking animation
                thinking_placeholder.empty()
                
                if result["status"] == "success":
                    # Display context source
                    context_source = result.get("context_source", "🤖 AI Response")
                    
                    # Check if response is empty or blank
                    response = result["response"].strip() if result.get("response") else ""
                    
                    if not response:
                        # Handle empty response case
                        error_message = "no such context document with given fields is available"
                        st.markdown(f'<div class="error-message">{error_message}</div>', unsafe_allow_html=True)
                        
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": error_message,
                            "error": True
                        })
                    else:
                        # Display context source and response
                        st.markdown(f'<div class="context-source">{context_source}</div>', unsafe_allow_html=True)
                        st.markdown(response)
                        
                        # Update session state
                        if result.get("new_df_result"):
                            st.session_state.df_result = result["new_df_result"]
                        
                        # Update QA history
                        st.session_state.qa_history.append((user_input, response))
                        
                        # Add assistant message to chat history
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": response,
                            "context_source": context_source
                        })
                        
                        # Update token count
                        if "token_count" in result:
                            st.session_state.total_tokens += result["token_count"]
                    
                else:
                    # Handle error
                    error_message = f"❌ Error: {result['message']}"
                    st.markdown(f'<div class="error-message">{error_message}</div>', unsafe_allow_html=True)
                    
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": error_message,
                        "error": True
                    })
                
            except Exception as e:
                thinking_placeholder.empty()
                error_message = f"❌ Unexpected error: {str(e)}"
                st.markdown(f'<div class="error-message">{error_message}</div>', unsafe_allow_html=True)
                
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": error_message,
                    "error": True
                })
    
    def render_chat_interface(self):
        """Render the main chat interface"""
        st.header("💭 Chat with Pod Placement AI Assistant")
        
        # Display chat history
        self.render_chat_history()
        
        # Chat input
        if prompt := st.chat_input("Ask Pod Placement AI Assistant about pod placement..."):
            self.process_user_input(prompt)
    
    def render_footer(self):
        """Render the footer"""
        st.divider()
        st.markdown("""
        <div style="text-align: center; color: #666; font-size: 0.9rem;">
            🤖 Pod Placement AI Assistant
        </div>
        """, unsafe_allow_html=True)
        
        # Optional: Display backend status in footer
        if st.session_state.backend_initialized:
            backend_status = self.backend.get_status()
            records = backend_status.get("data_records", {})
            st.markdown(f"""
            <div style="text-align: center; color: #999; font-size: 0.8rem; margin-top: 0.5rem;">
                📊 {records.get('dimensioning', 0)} Dimensioning Records | {records.get('pod_flavors', 0)} Pod Flavor Records
            </div>
            """, unsafe_allow_html=True)
    
    def run(self):
        """Main method to run the Streamlit application"""
        # Setup page configuration
        self.setup_page_config()
        
        # Apply custom CSS
        self.apply_custom_css()
        
        # Initialize session state
        self.initialize_session_state()
        
        # Render header
        self.render_header()
        
        # Initialize backend
        self.initialize_backend()
        
        # Render sidebar
        self.render_sidebar()
        
        # Render main chat interface
        self.render_chat_interface()
        
        # Render footer
        self.render_footer()


def main():
    """Main function to run the Pod Placement AI frontend"""
    try:
        frontend = NetTuneFrontend()
        frontend.run()
    except Exception as e:
        st.error(f"❌ Application Error: {str(e)}")
        st.stop()


if __name__ == "__main__":
    main()
