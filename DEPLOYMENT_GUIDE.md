# 🚀 BorsaCI Web App Deployment Guide

## ✅ What's Been Created

I've successfully created a Streamlit web application for BorsaCI with the following files:

1. **`streamlit_app.py`** - The main web application
2. **`STREAMLIT_README.md`** - Documentation and usage guide
3. **`requirements-streamlit.txt`** - Additional dependencies for Streamlit

## 📋 Step-by-Step Deployment Instructions

### Step 1: Push Code to Your GitHub Fork

```bash
# Navigate to your repository
cd /workspace

# Add the new files
git add streamlit_app.py STREAMLIT_README.md requirements-streamlit.txt

# Commit the changes
git commit -m "Add Streamlit web app for user-friendly interface"

# Push to your fork (DO NOT push upstream)
git push origin main
```

**⚠️ IMPORTANT**: This only pushes to YOUR forked repository, NOT to the original author's repository.

### Step 2: Deploy to Streamlit Cloud (Free)

1. **Go to [Streamlit Cloud](https://streamlit.io/cloud)**

2. **Sign in with GitHub**
   - Click "Sign in" → Select GitHub
   - Authorize Streamlit to access your repositories

3. **Create New App**
   - Click "New app" button
   - Select your repository from the dropdown (your fork of BorsaCI)
   - Configure:
     - **Branch**: `main` (or your branch name)
     - **Main file path**: `streamlit_app.py`
     - **Python version**: `3.11` or higher

4. **Click "Deploy!"**

### Step 3: Configure Custom Domain (borsaci.streamlit.app)

1. **In Streamlit Cloud Dashboard:**
   - Click on your deployed app
   - Go to "Settings" tab
   - Scroll to "Custom domain" section

2. **Enter Domain:**
   - Type: `borsaci.streamlit.app`
   - Click "Save"

3. **DNS Configuration:**
   - Streamlit will show you CNAME records to add
   - Go to your DNS provider (where you registered the domain)
   - Add the CNAME record as instructed
   - Wait 5-10 minutes for SSL certificate provisioning

### Step 4: Configure API Keys

**Option A: Using the Web Interface (Recommended)**
1. Open your deployed app at `https://borsaci.streamlit.app`
2. In the sidebar, enter your OpenRouter API key
3. Click "Save API Key"
4. Start chatting!

**Option B: Using Streamlit Secrets (More Secure)**
1. In Streamlit Cloud dashboard, go to your app
2. Click "Settings" → "Secrets"
3. Add your API key:
   ```toml
   OPENROUTER_API_KEY = "your-api-key-here"
   ```
4. Click "Save"

## 🎯 How to Use the Web App

### For End Users:

1. **Open the app**: Navigate to `https://borsaci.streamlit.app`

2. **Set up API key** (first time only):
   - Look at the left sidebar
   - Enter your OpenRouter API key
   - Click "Save"

3. **Start chatting**:
   - Type your question in Turkish or English
   - Examples:
     - "THYAO hissesini analiz et"
     - "Bitcoin fiyatı ne olur?"
     - "Türk Hava Yolları hakkında bilgi ver"

4. **View results**:
   - AI analysis appears in the chat
   - Charts display if applicable
   - Conversation history is saved

### Features:

- ✅ **Chat Interface**: Natural conversation with AI
- ✅ **Settings Panel**: Manage API keys securely
- ✅ **Provider Selection**: Switch between OpenRouter and Google OAuth
- ✅ **Chart Display**: Visual financial data
- ✅ **Turkish & English**: Multi-language support
- ✅ **Secure Storage**: API keys encrypted locally

## 🔧 Troubleshooting

### App Shows "Module Not Found" Error
**Solution**: Make sure all files are pushed to GitHub and Streamlit has finished deploying.

### Agent Not Responding
**Solutions**:
1. Check that API key is valid and has credits
2. Verify internet connection
3. Check Streamlit logs in the dashboard

### Import Errors
**Solution**: The app uses compatible package versions. If issues persist, check the deployment logs in Streamlit Cloud.

### Custom Domain Not Working
**Solutions**:
1. Wait 10-15 minutes after DNS changes
2. Clear browser cache
3. Verify CNAME record is correct in your DNS settings

## 💰 Cost Breakdown

| Service | Cost | Notes |
|---------|------|-------|
| Streamlit Cloud | **FREE** | Free tier includes 1000 app hours/month |
| Custom Domain | ~$10/year | If you don't already own borsaci.streamlit.app |
| OpenRouter API | Pay-per-use | ~$0.01-0.10 per query depending on model |
| GitHub | **FREE** | Free public/private repositories |

**Total Monthly Cost**: ~$0-5 (mostly API usage fees)

## 🔒 Security Best Practices

1. **Keep Your Fork Private** (if storing credentials)
   - Go to GitHub repo Settings → Danger Zone → Change visibility

2. **Never Commit API Keys**
   - Use Streamlit Secrets or the web interface
   - API keys are stored securely in `~/.borsaci/credentials/`

3. **Use HTTPS Only**
   - Streamlit Cloud provides free SSL certificates

4. **Regular Updates**
   - Keep your fork updated with security patches
   - Monitor API usage

## 📞 Support

If you encounter issues:

1. **Check Logs**: Streamlit Cloud dashboard → Logs
2. **Review Docs**: See `STREAMLIT_README.md`
3. **Test Locally**: Run `streamlit run streamlit_app.py` to debug

## 🎉 Next Steps

1. ✅ Push code to GitHub
2. ✅ Deploy to Streamlit Cloud
3. ✅ Configure custom domain
4. ✅ Test with sample queries
5. ✅ Share with users!

---

**Remember**: All changes stay in YOUR forked repository. Nothing is pushed to the original author's repository.
