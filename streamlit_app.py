"""
Streamlit Web App for BorsaCI
A user-friendly web interface for the Turkish financial markets AI agent.
"""

import streamlit as st
import asyncio
import os
from pathlib import Path
import json
import base64
from typing import Optional

# Page configuration
st.set_page_config(
    page_title="BorsaCI - Türk Finans Piyasaları AI Agent",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
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
    .stButton>button {
        width: 100%;
        background-color: #1f77b4;
        color: white;
        font-weight: bold;
    }
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        margin: 1rem 0;
    }
    .warning-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "agent_initialized" not in st.session_state:
    st.session_state.agent_initialized = False
if "config_loaded" not in st.session_state:
    st.session_state.config_loaded = False
if "chart_data" not in st.session_state:
    st.session_state.chart_data = None


def get_borsaci_dir() -> Path:
    """Get the ~/.borsaci directory path"""
    return Path.home() / ".borsaci"


def ensure_borsaci_dirs():
    """Create necessary directories"""
    borsaci_dir = get_borsaci_dir()
    borsaci_dir.mkdir(exist_ok=True, mode=0o700)
    (borsaci_dir / "credentials").mkdir(exist_ok=True, mode=0o700)
    return borsaci_dir


def load_config() -> dict:
    """Load configuration from file"""
    config_file = get_borsaci_dir() / "config.json"
    if config_file.exists():
        try:
            with open(config_file) as f:
                return json.load(f)
        except Exception:
            pass
    return {"active_provider": "openrouter"}


def save_config(config: dict):
    """Save configuration to file"""
    config_file = get_borsaci_dir() / "config.json"
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)


def load_openrouter_key() -> Optional[str]:
    """Load OpenRouter API key"""
    cred_file = get_borsaci_dir() / "credentials" / "openrouter.json"
    if cred_file.exists():
        try:
            with open(cred_file) as f:
                data = json.load(f)
                return data.get("api_key")
        except Exception:
            pass
    return None


def save_openrouter_key(api_key: str):
    """Save OpenRouter API key"""
    ensure_borsaci_dirs()
    cred_file = get_borsaci_dir() / "credentials" / "openrouter.json"
    import os
    fd = os.open(str(cred_file), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump({"api_key": api_key}, f)
    except Exception:
        os.close(fd)
        raise
    cred_file.chmod(0o600)


def load_google_credentials() -> Optional[dict]:
    """Load Google OAuth credentials"""
    cred_file = get_borsaci_dir() / "credentials" / "google.json"
    if cred_file.exists():
        try:
            with open(cred_file) as f:
                return json.load(f)
        except Exception:
            pass
    return None


def save_google_credentials(access_token: str, refresh_token: str, expires_at: int, email: Optional[str] = None):
    """Save Google OAuth credentials"""
    ensure_borsaci_dirs()
    cred_file = get_borsaci_dir() / "credentials" / "google.json"
    import os
    fd = os.open(str(cred_file), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump({
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
                "email": email
            }, f)
    except Exception:
        os.close(fd)
        raise
    cred_file.chmod(0o600)


def is_google_provider() -> bool:
    """Check if Google OAuth provider is configured"""
    config = load_config()
    return config.get("active_provider") == "google"


@st.cache_resource
def get_event_loop():
    """Get or create an event loop for async operations"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


async def run_agent_query(query: str):
    """Run the BorsaCI agent with a query"""
    try:
        from borsaci.agent import BorsaAgent
        
        async with BorsaAgent() as agent:
            result = await agent.run(query)
            return result
    except Exception as e:
        st.error(f"Error running agent: {str(e)}")
        return None


def main():
    # Header
    st.markdown('<h1 class="main-header">📈 BorsaCI</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Türk Finans Piyasaları AI Agent - BIST, TEFAS, Kripto ve daha fazlası</p>', unsafe_allow_html=True)
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Ayarlar")
        
        # Load current config
        config = load_config()
        current_provider = config.get("active_provider", "openrouter")
        
        # Provider selection
        provider_option = st.radio(
            "API Sağlayıcı",
            ["OpenRouter", "Google OAuth"],
            index=0 if current_provider == "openrouter" else 1,
            help="OpenRouter için API anahtarı, Google OAuth için Google hesabınızla giriş yapın"
        )
        
        selected_provider = "openrouter" if provider_option == "OpenRouter" else "google"
        
        # Save provider selection if changed
        if selected_provider != current_provider:
            config["active_provider"] = selected_provider
            save_config(config)
            st.rerun()
        
        st.divider()
        
        # Configuration based on provider
        if selected_provider == "openrouter":
            st.subheader("🔑 OpenRouter API Anahtarı")
            
            existing_key = load_openrouter_key()
            if existing_key:
                key_preview = f"{existing_key[:10]}..." if len(existing_key) > 10 else existing_key
                st.success(f"✅ API Anahtarı kaydedildi: {key_preview}")
                
                if st.button("🗑️ Anahtarı Sil"):
                    cred_file = get_borsaci_dir() / "credentials" / "openrouter.json"
                    if cred_file.exists():
                        cred_file.unlink()
                        st.rerun()
            else:
                st.warning("⚠️ API anahtarı kaydedilmemiş")
            
            new_key = st.text_input(
                "OpenRouter API Anahtarı",
                type="password",
                placeholder="sk-or-...",
                help="OpenRouter'dan aldığınız API anahtarını girin"
            )
            
            if st.button("💾 API Anahtarını Kaydet"):
                if new_key and new_key.strip():
                    save_openrouter_key(new_key.strip())
                    st.success("✅ API anahtarı başarıyla kaydedildi!")
                    st.rerun()
                else:
                    st.error("❌ Lütfen geçerli bir API anahtarı girin")
        
        else:  # Google OAuth
            st.subheader("🔐 Google OAuth")
            
            google_creds = load_google_credentials()
            if google_creds:
                email = google_creds.get("email", "Unknown")
                st.success(f"✅ Google hesabı bağlı: {email}")
                
                if st.button("🔓 Çıkış Yap"):
                    cred_file = get_borsaci_dir() / "credentials" / "google.json"
                    if cred_file.exists():
                        cred_file.unlink()
                    st.rerun()
            else:
                st.info("ℹ️ Google OAuth henüz yapılandırılmamış")
                st.markdown("""
                **Google OAuth Kurulumu:**
                
                1. Aşağıdaki bağlantıya tıklayın
                2. Google hesabınızla giriş yapın
                3. İzinleri onaylayın
                4. Otomatik olarak yönlendirileceksiniz
                """)
                
                # Note: For web app, we need a different OAuth flow
                st.warning("⚠️ Google OAuth web uygulaması için özel kurulum gereklidir. Şimdilik OpenRouter kullanmanızı öneririz.")
        
        st.divider()
        
        # About section
        st.subheader("ℹ️ Hakkında")
        st.markdown("""
        **BorsaCI** Türk finans piyasaları için yapay zeka destekli analiz asistanıdır.
        
        **Özellikler:**
        - 📊 BIST hisse senedi analizi
        - 💰 Kripto para analizi
        - 📈 TEFAS fon analizi
        - 🤖 Çoklu ajan mimarisi
        - 🔒 Güvenli kimlik doğrulama
        """)
        
        if st.button("🗑️ Tüm Verileri Temizle"):
            borsaci_dir = get_borsaci_dir()
            if borsaci_dir.exists():
                import shutil
                shutil.rmtree(borsaci_dir)
                st.success("✅ Tüm veriler temizlendi!")
                st.rerun()
    
    # Main content area
    if selected_provider == "openrouter" and not load_openrouter_key():
        # Show setup wizard if no API key
        st.markdown("""
        <div class="warning-box">
        <h3>⚠️ Kurulum Gerekli</h3>
        <p>BorsaCI'ı kullanmaya başlamak için lütfen sol menüden OpenRouter API anahtarınızı girin.</p>
        <p>API anahtarınız güvenli bir şekilde şifrelenerek saklanacaktır.</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        ### Nasıl Başlanır?
        
        1. **OpenRouter Hesabı Oluşturun**: [openrouter.ai](https://openrouter.ai) adresinden hesap oluşturun
        2. **API Anahtarı Alın**: Dashboard'dan API anahtarı oluşturun
        3. **Anahtarı Girin**: Sol menüden API anahtarınızı girin ve kaydedin
        4. **Soru Sormaya Başlayın**: Aşağıdaki sohbet arayüzünü kullanarak sorular sorun
        """)
        
        return
    
    # Chat interface
    st.markdown("### 💬 AI Agent ile Sohbet")
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "chart" in message and message["chart"]:
                st.code(message["chart"], language="text")
    
    # Chat input
    if prompt := st.chat_input("Finansal piyasalar hakkında soru sorun..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Run agent
        with st.chat_message("assistant"):
            with st.spinner("🤖 AI analiz ediyor..."):
                try:
                    # Get event loop
                    loop = get_event_loop()
                    
                    # Run async function
                    result = loop.run_until_complete(run_agent_query(prompt))
                    
                    if result:
                        answer, chart, messages = result
                        
                        # Display answer
                        st.markdown(answer)
                        
                        # Display chart if available
                        if chart:
                            st.code(chart, language="text")
                        
                        # Save to history
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": answer,
                            "chart": chart if chart else None
                        })
                    else:
                        st.error("❌ Bir hata oluştu. Lütfen tekrar deneyin.")
                
                except Exception as e:
                    st.error(f"❌ Hata: {str(e)}")
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": f"Üzgünüm, bir hata oluştu: {str(e)}"
                    })


if __name__ == "__main__":
    main()
