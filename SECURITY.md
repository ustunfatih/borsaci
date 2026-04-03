# Security Guidelines for BorsaCI

This document outlines security best practices and known security considerations for BorsaCI.

## 🔐 Credential Management

### OAuth Credentials (Google)

**IMPORTANT**: As of this version, hardcoded OAuth credentials have been removed for security reasons.

You must now use one of these methods to authenticate with Google:

#### Method 1: Gemini CLI Integration (Recommended)
If you have Gemini CLI installed and logged in, BorsaCI will automatically reuse those credentials:
```bash
gemini login  # Log in to Gemini CLI first
borsaci       # BorsaCI will automatically detect and use the tokens
```

#### Method 2: Environment Variables
Set your own Google Cloud OAuth credentials via environment variables:
```bash
export BORSA_OAUTH_CLIENT_ID="your-client-id.apps.googleusercontent.com"
export BORSA_OAUTH_CLIENT_SECRET="your-client-secret"
borsaci
```

To get OAuth credentials:
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable "Generative Language API"
4. Go to "Credentials" → "Create Credentials" → "OAuth client ID"
5. Choose "Desktop app" as application type
6. Save the client ID and secret

### OpenRouter API Key

Store your OpenRouter API key securely:
- Use `.env` file (created automatically during setup)
- Or set environment variable: `export OPENROUTER_API_KEY="sk-or-v1-..."`

## 📁 File Permissions

BorsaCI stores sensitive credentials in `~/.borsaci/`:
- `~/.borsaci/config.json` - Configuration (mode 700)
- `~/.borsaci/credentials/openrouter.json` - OpenRouter key (mode 600)
- `~/.borsaci/credentials/google.json` - Google OAuth tokens (mode 600)

These files are created with restrictive permissions (owner read/write only).

## 🛡️ Security Improvements in This Version

### Fixed Vulnerabilities

1. **Removed Hardcoded Credentials** (HIGH)
   - Base64-encoded OAuth credentials removed from source code
   - Users must now provide their own credentials

2. **Secure File Permissions** (MEDIUM)
   - Race condition fixed in credential file creation
   - Files created with restricted mode from the start using `os.open()` with mode flags

3. **OAuth Callback Security** (MEDIUM)
   - Server now binds to `127.0.0.1` instead of `localhost` (explicit IPv4)
   - Added IP validation to reject non-localhost requests
   - CSRF protection via state parameter validation

4. **Debug Information Leakage** (MEDIUM)
   - API keys no longer exposed in debug logs
   - Key previews replaced with `***REDACTED***`

5. **SSL/TLS Verification** (LOW)
   - Explicit SSL certificate verification enabled for GitHub API calls
   - Prevents MITM attacks on update checks

6. **Improved Exception Handling** (LOW)
   - Replaced bare `except Exception:` with specific exception types
   - Better error categorization for security-relevant failures

## 🔒 Best Practices

1. **Never commit credentials** to version control
2. **Use environment variables** in production deployments
3. **Rotate credentials regularly**, especially if compromised
4. **Keep dependencies updated** for security patches
5. **Review logs** for suspicious activity when running in debug mode

## ⚠️ Known Limitations

1. **HTTP OAuth Callback**: The OAuth callback uses HTTP on localhost (not HTTPS). This is acceptable for local development but be aware of the limitation.

2. **Plaintext Storage**: Credentials are stored in plaintext JSON files (with restricted permissions). For enhanced security, consider using system keyrings or secret management tools.

3. **No Rate Limiting**: OAuth flows don't implement rate limiting. Be cautious of API quotas.

## 📞 Reporting Security Issues

If you discover a security vulnerability, please report it responsibly by opening an issue in your forked repository. Do not report security issues to the upstream repository.

---

**Note**: This fork maintains independent security updates. Changes made here are not contributed back to the original author.
