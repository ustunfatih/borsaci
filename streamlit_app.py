"""
BorsaCI - AI-Powered Turkish Financial Markets Assistant
Modern Streamlit web interface with multi-provider LLM support.
"""

import streamlit as st
import httpx
import json
from datetime import datetime

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="BorsaCI – AI Borsa Asistanı",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Modern CSS theme ──────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* ---- Global ---- */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

  /* ---- Hero header ---- */
  .hero {
    background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%);
    border-radius: 16px;
    padding: 2rem 2.5rem 1.75rem;
    margin-bottom: 1.5rem;
    color: #fff;
  }
  .hero h1 { margin: 0; font-size: 2rem; font-weight: 700; letter-spacing: -0.5px; }
  .hero p  { margin: 0.35rem 0 0; font-size: 1rem; opacity: 0.75; }

  /* ---- Pill badges ---- */
  .badge {
    display: inline-block;
    padding: 0.2rem 0.65rem;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    margin-right: 0.4rem;
  }
  .badge-green  { background: #d1fae5; color: #065f46; }
  .badge-blue   { background: #dbeafe; color: #1e40af; }
  .badge-orange { background: #ffedd5; color: #9a3412; }

  /* ---- Quick action chips ---- */
  .chip-row { display: flex; flex-wrap: wrap; gap: 0.5rem; margin: 1rem 0 0.5rem; }

  /* ---- Rate-limit callout ---- */
  .rl-box {
    background: #fff7ed;
    border-left: 4px solid #f97316;
    border-radius: 8px;
    padding: 0.85rem 1rem;
    font-size: 0.9rem;
    line-height: 1.6;
  }

  /* ---- Sidebar tweaks ---- */
  section[data-testid="stSidebar"] { background: #0f172a; }
  section[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
  section[data-testid="stSidebar"] .stSelectbox label,
  section[data-testid="stSidebar"] .stRadio label { color: #94a3b8 !important; font-size: 0.78rem !important; text-transform: uppercase; letter-spacing: 0.05em; }
  section[data-testid="stSidebar"] hr { border-color: #1e293b !important; }

  /* ---- Input box ---- */
  .stChatInput textarea { border-radius: 12px !important; }

  /* ---- Scrollbar ---- */
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: #475569; border-radius: 3px; }
</style>
""", unsafe_allow_html=True)

# ── Constants ────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Sen BorsaCI'sın – Borsa İstanbul ve Türk finansal piyasaları konusunda uzmanlaşmış bir yapay zeka asistanısın.

Görevlerin:
- BIST hisse senetleri, TEFAS yatırım fonları, kripto para ve döviz analizleri yapmak
- Teknik ve temel analiz yorumları sunmak
- Piyasa haberlerini ve makroekonomik verileri değerlendirmek
- Yatırım kararlarında kullanılacak bilgiler sağlamak (tavsiye değil, bilgi)

Kurallar:
- Kullanıcının dilinde (Türkçe veya İngilizce) yanıt ver
- Net, özlü ve profesyonel ol
- Finansal tavsiye vermediğini gerektiğinde belirt
- Güncel verilere erişimin olmadığında bunu açıkça söyle
"""

# Provider → model options  (label, model_id, free?)
PROVIDERS = {
    "groq": {
        "label": "Groq (Ücretsiz & Hızlı)",
        "badge": "badge-green",
        "badge_text": "ÜCRETSİZ",
        "models": [
            ("Llama 3.3 70B – Önerilen", "llama-3.3-70b-versatile"),
            ("Llama 3.1 70B", "llama-3.1-70b-versatile"),
            ("Mixtral 8x7B", "mixtral-8x7b-32768"),
            ("Gemma 2 9B", "gemma2-9b-it"),
        ],
        "key_label": "Groq API Anahtarı",
        "key_help": "Groq Console'dan ücretsiz alın",
        "key_placeholder": "gsk_...",
        "key_secret": "groq_key",
    },
    "openrouter": {
        "label": "OpenRouter (Çok Model)",
        "badge": "badge-blue",
        "badge_text": "ÜCRETSİZ MODELLER VAR",
        "models": [
            ("DeepSeek V3 – Ücretsiz", "deepseek/deepseek-chat-v3-0324:free"),
            ("Llama 4 Scout – Ücretsiz", "meta-llama/llama-4-scout:free"),
            ("Qwen3 235B – Ücretsiz", "qwen/qwen3-235b-a22b:free"),
            ("Mistral Small 3.1 – Ücretsiz", "mistralai/mistral-small-3.1-24b-instruct:free"),
            ("Gemini 2.0 Flash – Ücretsiz", "google/gemini-2.0-flash-exp:free"),
            ("Gemini 2.5 Pro (Ücretli)", "google/gemini-2.5-pro-preview-03-25"),
        ],
        "key_label": "OpenRouter API Anahtarı",
        "key_help": "openrouter.ai/keys adresinden alın",
        "key_placeholder": "sk-or-v1-...",
        "key_secret": "openrouter_key",
    },
    "gemini": {
        "label": "Google Gemini (Doğrudan)",
        "badge": "badge-orange",
        "badge_text": "KOTA SINIRI VAR",
        "models": [
            ("Gemini 2.0 Flash", "gemini-2.0-flash"),
            ("Gemini 2.5 Flash Preview", "gemini-2.5-flash-preview-04-17"),
            ("Gemini 1.5 Flash", "gemini-1.5-flash"),
        ],
        "key_label": "Gemini API Anahtarı",
        "key_help": "aistudio.google.com/app/apikey adresinden alın",
        "key_placeholder": "AIza...",
        "key_secret": "gemini_key",
    },
}

QUICK_PROMPTS = [
    ("📊 BIST 100 özet", "Bugün BIST 100 endeksi hakkında genel bir değerlendirme yapar mısın?"),
    ("🏦 Dolar/TL analiz", "Dolar/TL paritesi için kısa vadeli teknik analiz yapabilir misin?"),
    ("⛏️ Kripto piyasa", "Kripto para piyasasında güncel durum nedir?"),
    ("🛡️ Buffett stratejisi", "Warren Buffett'ın değer yatırımı yaklaşımını Türk borsasına nasıl uygulayabilirim?"),
    ("📈 Teknoloji hisseleri", "BIST'te öne çıkan teknoloji hisseleri hangileri?"),
    ("💰 Enflasyon koruması", "Türkiye'deki yüksek enflasyona karşı portföyümü nasıl koruyabilirim?"),
]

# ── Helpers ──────────────────────────────────────────────────────────────────

def _secrets_get(key: str) -> str:
    try:
        return st.secrets.get("credentials", {}).get(key, "")
    except Exception:
        return ""


def _is_rate_limit(status_code: int, body: str) -> bool:
    return status_code == 429 or "rate" in body.lower() or "quota" in body.lower()


def _rate_limit_message(provider: str) -> str:
    tips = {
        "gemini": (
            "**Gemini API kota sınırına ulaşıldı.** Ücretsiz katmanda dakikada 15, günde 1500 istek limiti vardır.\n\n"
            "**Alternatifler:**\n"
            "- 🟢 **Groq** (önerilen) – dakikada 30 istek, günde 14.400 istek ücretsiz. `gsk_` ile başlayan anahtar.\n"
            "- 🔵 **OpenRouter** – `DeepSeek V3 :free` veya `Llama 4 Scout :free` modelleri tamamen ücretsiz.\n"
            "- ⏳ Birkaç dakika bekleyip tekrar deneyin."
        ),
        "openrouter": (
            "**OpenRouter model kota sınırı.** Ücretsiz modellerde günlük limit uygulanabilir.\n\n"
            "**Öneriler:**\n"
            "- Listeden farklı bir ücretsiz model seçin.\n"
            "- 🟢 **Groq** ile devam edin – çok daha hızlı ve ücretsiz.\n"
            "- Ücretli bir OpenRouter modeline geçin."
        ),
        "groq": (
            "**Groq kota sınırı.** Ücretsiz katmanda dakikada 30 istek vardır.\n\n"
            "**Öneriler:**\n"
            "- Birkaç saniye bekleyip tekrar deneyin.\n"
            "- 🔵 **OpenRouter** ücretsiz modellerine geçin.\n"
            "- Farklı bir Groq modeli deneyin."
        ),
    }
    return tips.get(provider, "API kota sınırına ulaşıldı. Lütfen farklı bir sağlayıcı deneyin.")


# ── API callers ───────────────────────────────────────────────────────────────

def call_groq(message: str, api_key: str, model: str, history: list) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in history[-12:]:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": message})

    try:
        r = httpx.post(
            url,
            json={"model": model, "messages": messages, "temperature": 0.7, "max_tokens": 2048},
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=45.0,
        )
        if _is_rate_limit(r.status_code, r.text):
            return "__RATE_LIMIT__"
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as e:
        if _is_rate_limit(e.response.status_code, e.response.text):
            return "__RATE_LIMIT__"
        return f"API hatası ({e.response.status_code}): İstek başarısız oldu."
    except Exception as e:
        return f"Bağlantı hatası: {type(e).__name__}"


def call_openrouter(message: str, api_key: str, model: str, history: list) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in history[-12:]:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": message})

    try:
        r = httpx.post(
            url,
            json={"model": model, "messages": messages, "temperature": 0.7, "max_tokens": 2048},
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://borsaci.streamlit.app",
                "X-Title": "BorsaCI",
            },
            timeout=60.0,
        )
        if _is_rate_limit(r.status_code, r.text):
            return "__RATE_LIMIT__"
        r.raise_for_status()
        data = r.json()
        if "choices" in data and data["choices"]:
            return data["choices"][0]["message"]["content"]
        if "error" in data:
            err = data["error"]
            if isinstance(err, dict) and _is_rate_limit(err.get("code", 0), err.get("message", "")):
                return "__RATE_LIMIT__"
            return f"Model hatası: {err}"
        return "Yanıt alınamadı."
    except httpx.HTTPStatusError as e:
        if _is_rate_limit(e.response.status_code, e.response.text):
            return "__RATE_LIMIT__"
        return f"API hatası ({e.response.status_code}): İstek başarısız oldu."
    except Exception as e:
        return f"Bağlantı hatası: {type(e).__name__}"


def call_gemini(message: str, api_key: str, model: str, history: list) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    contents = []
    for m in history[-12:]:
        role = "user" if m["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})
    contents.append({"role": "user", "parts": [{"text": message}]})

    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.7, "topK": 40, "topP": 0.95, "maxOutputTokens": 2048},
    }

    try:
        r = httpx.post(
            f"{url}?key={api_key}",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=45.0,
        )
        if _is_rate_limit(r.status_code, r.text):
            return "__RATE_LIMIT__"
        r.raise_for_status()
        data = r.json()
        if "candidates" in data and data["candidates"]:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        return "Yanıt oluşturulamadı."
    except httpx.HTTPStatusError as e:
        if _is_rate_limit(e.response.status_code, e.response.text):
            return "__RATE_LIMIT__"
        return f"API hatası ({e.response.status_code}): İstek başarısız oldu."
    except Exception as e:
        return f"Bağlantı hatası: {type(e).__name__}"


def call_api(provider: str, message: str, api_key: str, model: str, history: list) -> str:
    if provider == "groq":
        return call_groq(message, api_key, model, history)
    elif provider == "openrouter":
        return call_openrouter(message, api_key, model, history)
    else:
        return call_gemini(message, api_key, model, history)


# ── Main app ──────────────────────────────────────────────────────────────────

def main():
    # ── Session state defaults ────────────────────────────────────────────────
    defaults = {
        "messages": [],
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "api_key": "",
        "show_welcome": True,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("## 📈 BorsaCI")
        st.markdown("*AI Borsa Asistanı*")
        st.markdown("---")

        # Provider selection
        st.markdown("##### API Sağlayıcı")
        provider_labels = {k: v["label"] for k, v in PROVIDERS.items()}
        selected_provider = st.selectbox(
            "Sağlayıcı seç",
            options=list(provider_labels.keys()),
            format_func=lambda x: provider_labels[x],
            index=list(provider_labels.keys()).index(st.session_state.provider),
            label_visibility="collapsed",
        )
        if selected_provider != st.session_state.provider:
            st.session_state.provider = selected_provider
            # Reset model to first option for new provider
            st.session_state.model = PROVIDERS[selected_provider]["models"][0][1]
            st.rerun()

        cfg = PROVIDERS[st.session_state.provider]

        # Badge
        st.markdown(
            f'<span class="badge {cfg["badge"]}">{cfg["badge_text"]}</span>',
            unsafe_allow_html=True,
        )

        st.markdown("---")

        # Model selection
        st.markdown("##### Model")
        model_options = cfg["models"]
        model_labels = [m[0] for m in model_options]
        model_ids    = [m[1] for m in model_options]
        current_idx  = model_ids.index(st.session_state.model) if st.session_state.model in model_ids else 0
        selected_model_idx = st.selectbox(
            "Model seç",
            options=range(len(model_labels)),
            format_func=lambda i: model_labels[i],
            index=current_idx,
            label_visibility="collapsed",
        )
        st.session_state.model = model_ids[selected_model_idx]

        st.markdown("---")

        # API Key
        st.markdown(f"##### {cfg['key_label']}")
        stored_key = _secrets_get(cfg["key_secret"])
        api_key = st.text_input(
            "api_key_input",
            type="password",
            value=stored_key or st.session_state.api_key,
            placeholder=cfg["key_placeholder"],
            help=cfg["key_help"],
            label_visibility="collapsed",
        )
        if api_key:
            st.session_state.api_key = api_key
            st.markdown('<span class="badge badge-green">✓ Anahtar girildi</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="badge badge-orange">⚠ Anahtar gerekli</span>', unsafe_allow_html=True)

        st.markdown("---")

        # Stats
        msg_count = len(st.session_state.messages)
        user_count = sum(1 for m in st.session_state.messages if m["role"] == "user")
        col1, col2 = st.columns(2)
        col1.metric("Mesaj", msg_count)
        col2.metric("Sorgu", user_count)

        st.markdown("---")

        # Actions
        if st.button("🗑️ Sohbeti Temizle", use_container_width=True):
            st.session_state.messages = []
            st.session_state.show_welcome = True
            st.rerun()

        if st.session_state.messages:
            chat_export = json.dumps(st.session_state.messages, ensure_ascii=False, indent=2)
            st.download_button(
                "💾 Sohbeti İndir",
                data=chat_export,
                file_name=f"borsaci_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                mime="application/json",
                use_container_width=True,
            )

        st.markdown("---")
        st.markdown(
            '<div style="font-size:0.7rem;opacity:0.45;text-align:center">'
            'BorsaCI – Yatırım tavsiyesi değildir</div>',
            unsafe_allow_html=True,
        )

    # ── Main area ─────────────────────────────────────────────────────────────

    # Hero header
    st.markdown(
        """
        <div class="hero">
          <h1>📈 BorsaCI</h1>
          <p>Borsa İstanbul ve Türk finansal piyasaları için yapay zeka destekli analiz asistanı</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Gate on API key
    if not st.session_state.api_key:
        st.info(
            f"**Başlamak için sol menüden API anahtarı girin.**\n\n"
            f"🟢 **Groq** en hızlı ve ücretsiz seçenektir – [groq.com/keys](https://console.groq.com/keys) adresinden saniyeler içinde anahtar alabilirsiniz.",
            icon="🔑",
        )
        st.stop()

    # Welcome screen with quick prompts
    if st.session_state.show_welcome and not st.session_state.messages:
        st.markdown("#### Hızlı Başlangıç")
        cols = st.columns(3)
        for i, (label, prompt) in enumerate(QUICK_PROMPTS):
            if cols[i % 3].button(label, use_container_width=True, key=f"qp_{i}"):
                st.session_state.show_welcome = False
                _send_message(prompt)
                st.rerun()

    # Chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg.get("is_error"):
                st.markdown(
                    f'<div class="rl-box">{msg["content"]}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(msg["content"])

    # Chat input
    if user_input := st.chat_input("Borsa İstanbul hakkında soru sorun…"):
        st.session_state.show_welcome = False
        _send_message(user_input)
        st.rerun()


def _send_message(prompt: str):
    """Append user message, call API, append assistant reply."""
    provider = st.session_state.provider
    model    = st.session_state.model
    api_key  = st.session_state.api_key

    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analiz ediliyor…"):
            response = call_api(provider, prompt, api_key, model, st.session_state.messages)

    if response == "__RATE_LIMIT__":
        msg = _rate_limit_message(provider)
        st.session_state.messages.append({"role": "assistant", "content": msg, "is_error": True})
    else:
        st.session_state.messages.append({"role": "assistant", "content": response})


if __name__ == "__main__":
    main()
