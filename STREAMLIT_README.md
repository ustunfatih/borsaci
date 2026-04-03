# Streamlit Web App for BorsaCI

This directory contains the Streamlit web application for BorsaCI.

## Quick Start

### Local Development

1. **Install dependencies:**
   ```bash
   pip install streamlit
   ```

2. **Run the app:**
   ```bash
   streamlit run streamlit_app.py
   ```

3. **Access the app:**
   Open your browser to `http://localhost:8501`

### Deploy to Streamlit Cloud (Free)

1. **Push your code to GitHub** (your forked repository)

2. **Go to [Streamlit Cloud](https://streamlit.io/cloud)**

3. **Connect your GitHub repository:**
   - Click "New app"
   - Select your repository
   - Set Branch: `main` (or your branch name)
   - Set Main file path: `streamlit_app.py`

4. **Configure secrets (IMPORTANT):**
   - In Streamlit Cloud dashboard, click on your app
   - Go to "Settings" → "Secrets"
   - Add your API keys:
     ```toml
     [openrouter]
     api_key = "your-openrouter-api-key-here"
     ```

5. **Deploy!**
   - Click "Deploy"
   - Your app will be available at: `https://borsaci.streamlit.app`

## Features

- 💬 **Chat Interface**: Natural language conversation with the AI agent
- ⚙️ **Settings Panel**: Configure API keys and providers
- 🔒 **Secure Storage**: API keys encrypted and stored securely
- 📊 **Chart Display**: Visual charts for financial data
- 🌐 **Multi-language**: Turkish and English support

## Configuration

### OpenRouter (Recommended for Web)

1. Get an API key from [openrouter.ai](https://openrouter.ai)
2. Enter it in the Settings panel
3. Start chatting!

### Google OAuth (Advanced)

Google OAuth requires additional setup for web deployment:

1. Create a Google Cloud Project
2. Enable Google Drive API
3. Create OAuth credentials
4. Configure authorized redirect URIs
5. Update `streamlit_app.py` with your credentials

For simplicity, we recommend using OpenRouter for the web app.

## Custom Domain

To use `borsaci.streamlit.app`:

1. Deploy to Streamlit Cloud
2. Go to app Settings
3. Under "Custom domain", enter `borsaci.streamlit.app`
4. Follow DNS configuration instructions
5. Wait for SSL certificate provisioning (~5 minutes)

## Troubleshooting

### App won't start
- Check that all dependencies are installed
- Verify API keys are correctly configured
- Check Streamlit Cloud logs for errors

### Agent not responding
- Ensure API key is valid and has credits
- Check network connectivity
- Review error messages in the chat

### Charts not displaying
- Some queries may not generate charts
- Charts are displayed as text-based visualizations

## Security Notes

- API keys are stored securely with file permissions 600
- Never commit API keys to version control
- Use environment variables or Streamlit Secrets for production
- Keep your fork private if storing sensitive credentials

## Support

For issues or questions:
- Check the main BorsaCI repository documentation
- Review Streamlit documentation
- Contact the maintainer
