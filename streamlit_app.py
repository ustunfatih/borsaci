"""
Streamlit Web App for BorsaCI
A user-friendly web interface for the Turkish financial markets AI agent.
"""

import streamlit as st
import httpx
import base64
import json
import os
from datetime import datetime

# Page config
st.set_page_config(
    page_title="BorsaCI - AI Trading Assistant",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {font-size: 2.5rem; font-weight: bold; color: #1f77b4;}
    .sub-header {font-size: 1.2rem; color: #666;}
    .chat-message {padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;}
    .user-message {background-color: #e3f2fd;}
    .bot-message {background-color: #f5f5f5;}
    .stButton>button {width: 100%;}
</style>
""", unsafe_allow_html=True)

def get_stored_credentials():
    """Get credentials from Streamlit secrets or session state"""
    if hasattr(st, 'secrets') and 'credentials' in st.secrets:
        return st.secrets['credentials']
    return None

def save_to_secrets(gemini_key=None, openrouter_key=None, oauth_token=None):
    """Note: In Streamlit Cloud, we can't write to secrets programmatically.
    Users must set them in the dashboard."""
    pass

def call_gemini_api(message, api_key, history=None):
    """Call Google Gemini API directly"""
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    
    system_instruction = """You are BorsaCI, an AI-powered trading assistant specialized in Turkish stock market (Borsa Istanbul). 
    You provide analysis, insights, and information about stocks listed on BIST. 
    Always respond in the same language as the user's query (Turkish or English).
    Be concise, accurate, and professional."""
    
    contents = []
    if history:
        for msg in history[-10:]:  # Last 10 messages
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
    
    contents.append({"role": "user", "parts": [{"text": message}]})
    
    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "topK": 40,
            "topP": 0.95,
            "maxOutputTokens": 1024,
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]
    }
    
    headers = {"Content-Type": "application/json"}
    
    try:
        response = httpx.post(
            f"{url}?key={api_key}",
            json=payload,
            headers=headers,
            timeout=30.0
        )
        response.raise_for_status()
        result = response.json()
        
        if "candidates" in result and len(result["candidates"]) > 0:
            return result["candidates"][0]["content"]["parts"][0]["text"]
        else:
            return "No response generated. Please try again."
            
    except httpx.HTTPStatusError as e:
        return f"API Error: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        return f"Error: {str(e)}"

def call_openrouter_api(message, api_key, history=None):
    """Call OpenRouter API directly"""
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    system_prompt = """You are BorsaCI, an AI-powered trading assistant specialized in Turkish stock market (Borsa Istanbul)."""
    
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        for msg in history[-10:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": message})
    
    payload = {
        "model": "google/gemini-2.0-flash-exp:free",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1024,
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://borsaci.streamlit.app",
        "X-Title": "BorsaCI"
    }
    
    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=30.0)
        response.raise_for_status()
        result = response.json()
        
        if "choices" in result and len(result["choices"]) > 0:
            return result["choices"][0]["message"]["content"]
        else:
            return "No response generated."
            
    except Exception as e:
        return f"Error: {str(e)}"

def main():
    st.title("📈 BorsaCI - AI Trading Assistant")
    st.markdown("Your intelligent companion for Borsa Istanbul analysis")
    
    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "api_provider" not in st.session_state:
        st.session_state.api_provider = "gemini"
    
    # Sidebar for settings
    with st.sidebar:
        st.header("⚙️ Settings")
        
        # API Provider Selection
        provider = st.radio(
            "Select API Provider",
            ["Google Gemini", "OpenRouter"],
            index=0 if st.session_state.api_provider == "gemini" else 1
        )
        st.session_state.api_provider = "gemini" if provider == "Google Gemini" else "openrouter"
        
        st.markdown("---")
        
        # Get API Keys from Streamlit Secrets or user input
        secrets = get_stored_credentials()
        
        if st.session_state.api_provider == "gemini":
            api_key = st.text_input(
                "Gemini API Key",
                type="password",
                value=secrets.get("gemini_key", "") if secrets else "",
                help="Get your key from https://aistudio.google.com/app/apikey"
            )
            if api_key:
                st.success("✓ API Key provided")
            else:
                st.warning("⚠️ Please enter your Gemini API Key")
                
        else:  # OpenRouter
            api_key = st.text_input(
                "OpenRouter API Key",
                type="password",
                value=secrets.get("openrouter_key", "") if secrets else "",
                help="Get your key from https://openrouter.ai/keys"
            )
            if api_key:
                st.success("✓ API Key provided")
            else:
                st.warning("⚠️ Please enter your OpenRouter API Key")
        
        st.markdown("---")
        st.info("**Pro Tip:** For permanent storage, set your API keys in Streamlit Cloud Dashboard → Settings → Secrets")
        
        # Clear chat button
        if st.button("🗑️ Clear Chat History"):
            st.session_state.messages = []
            st.rerun()
    
    # Check if API key is available
    if not api_key:
        st.warning("⚠️ Please enter your API key in the sidebar to start chatting.")
        st.stop()
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask about Borsa Istanbul stocks..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Analyzing market data..."):
                if st.session_state.api_provider == "gemini":
                    response = call_gemini_api(
                        prompt, 
                        api_key, 
                        st.session_state.messages
                    )
                else:
                    response = call_openrouter_api(
                        prompt, 
                        api_key, 
                        st.session_state.messages
                    )
                
                st.markdown(response)
        
        # Add assistant response
        st.session_state.messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    main()
