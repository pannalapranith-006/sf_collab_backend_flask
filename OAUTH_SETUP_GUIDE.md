# OAuth Setup & Frontend Integration Guide

## Current Status ✅

Your OAuth implementation is **READY** but needs credentials configured. Here's what you have:

### Backend Status
- ✅ Google OAuth routes implemented (`/api/auth/google/login`, `/api/auth/google/callback`)
- ✅ GitHub OAuth routes implemented (`/api/auth/github/login`, `/api/auth/github/callback`)
- ✅ OAuth library (Authlib) configured
- ✅ User creation/login flow ready
- ✅ Token generation working
- ✅ Callback handlers with postMessage to frontend
- ⚠️ **Missing: OAuth credentials in `.env` file**

---

## 🔧 Step 1: Create `.env` File

You don't have a `.env` file. Create one:

```bash
cp .env.example .env
```

Then edit `.env` and add your OAuth credentials (see steps 2-3 below).

---

## 🔑 Step 2: Get Google OAuth Credentials

### 2.1 Create Google OAuth App

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Navigate to **APIs & Services** → **Credentials**
4. Click **Create Credentials** → **OAuth client ID**
5. Choose **Web application**

### 2.2 Configure OAuth Consent Screen

Before creating credentials, configure the consent screen:
- Go to **OAuth consent screen**
- Choose **External** (unless you have Google Workspace)
- Fill in:
  - App name: "SF Collab"
  - User support email
  - Developer contact email
- Add scopes: `email`, `profile`, `openid`
- Add test users during development

### 2.3 Set Authorized Redirect URIs

Add these redirect URIs based on your environment:

**Development:**
```
http://localhost:5000/api/auth/google/callback
http://127.0.0.1:5000/api/auth/google/callback
```

**Production (if deployed):**
```
https://your-domain.com/api/auth/google/callback
```

### 2.4 Get Credentials

After creating the OAuth client:
- Copy **Client ID**
- Copy **Client secret**

Add to `.env`:
```bash
GOOGLE_CLIENT_ID=your-actual-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-actual-client-secret
```

---

## 🔑 Step 3: Get GitHub OAuth Credentials

### 3.1 Create GitHub OAuth App

1. Go to [GitHub Developer Settings](https://github.com/settings/developers)
2. Click **OAuth Apps** → **New OAuth App**

### 3.2 Fill in Application Details

- **Application name:** SF Collab
- **Homepage URL:** 
  - Dev: `http://localhost:5000`
  - Prod: `https://your-domain.com`
- **Authorization callback URL:**
  - Dev: `http://localhost:5000/api/auth/github/callback`
  - Prod: `https://your-domain.com/api/auth/github/callback`

### 3.3 Get Credentials

After creating:
- Copy **Client ID**
- Generate and copy **Client Secret**

Add to `.env`:
```bash
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret
```

---

## 🌐 Step 4: Frontend Integration

### 4.1 OAuth Flow Overview

```
User clicks "Login with Google/GitHub"
    ↓
Frontend opens popup window to backend OAuth URL
    ↓
User authenticates with Google/GitHub
    ↓
Backend receives callback and creates/logs in user
    ↓
Backend returns HTML with postMessage to parent window
    ↓
Frontend receives message with tokens & user data
    ↓
Frontend stores tokens and redirects user
```

### 4.2 Frontend Implementation (React Example)

Create an OAuth helper file:

```javascript
// utils/oauth.js

export const initiateOAuth = (provider) => {
  const backendURL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:5000';
  const authURL = `${backendURL}/api/auth/${provider}/login`;
  
  // Open popup window
  const popup = window.open(
    authURL,
    `${provider}_oauth`,
    'width=600,height=700,left=100,top=100'
  );
  
  // Return promise that resolves when OAuth completes
  return new Promise((resolve, reject) => {
    // Listen for message from popup
    const messageHandler = (event) => {
      // IMPORTANT: Verify origin in production
      // if (event.origin !== backendURL) return;
      
      const data = event.data;
      
      if (data.type === 'oauth_success') {
        // Clean up
        window.removeEventListener('message', messageHandler);
        popup.close();
        
        // Resolve with auth data
        resolve({
          accessToken: data.access_token,
          refreshToken: data.refreshToken,
          user: data.user,
          provider: data.provider,
          isNewUser: data.is_new_user
        });
      } else if (data.type === 'oauth_error') {
        // Clean up
        window.removeEventListener('message', messageHandler);
        popup.close();
        
        // Reject with error
        reject(new Error(data.error));
      }
    };
    
    window.addEventListener('message', messageHandler);
    
    // Handle popup closed before completion
    const checkPopup = setInterval(() => {
      if (popup.closed) {
        clearInterval(checkPopup);
        window.removeEventListener('message', messageHandler);
        reject(new Error('OAuth popup closed'));
      }
    }, 1000);
  });
};
```

### 4.3 Use in Your Login Component

```javascript
// components/Login.jsx
import { initiateOAuth } from '../utils/oauth';
import { useNavigate } from 'react-router-dom';

function Login() {
  const navigate = useNavigate();
  
  const handleGoogleLogin = async () => {
    try {
      const authData = await initiateOAuth('google');
      
      // Store tokens
      localStorage.setItem('accessToken', authData.accessToken);
      localStorage.setItem('refreshToken', authData.refreshToken);
      localStorage.setItem('user', JSON.stringify(authData.user));
      
      // Navigate to dashboard
      navigate('/dashboard');
      
      // Show welcome message if new user
      if (authData.isNewUser) {
        alert('Welcome! Your account has been created.');
      }
    } catch (error) {
      console.error('Google OAuth failed:', error);
      alert('Login failed. Please try again.');
    }
  };
  
  const handleGitHubLogin = async () => {
    try {
      const authData = await initiateOAuth('github');
      
      // Store tokens
      localStorage.setItem('accessToken', authData.accessToken);
      localStorage.setItem('refreshToken', authData.refreshToken);
      localStorage.setItem('user', JSON.stringify(authData.user));
      
      // Navigate to dashboard
      navigate('/dashboard');
      
      if (authData.isNewUser) {
        alert('Welcome! Your account has been created.');
      }
    } catch (error) {
      console.error('GitHub OAuth failed:', error);
      alert('Login failed. Please try again.');
    }
  };
  
  return (
    <div>
      <button onClick={handleGoogleLogin}>
        Login with Google
      </button>
      <button onClick={handleGitHubLogin}>
        Login with GitHub
      </button>
    </div>
  );
}
```

### 4.4 Environment Variables (Frontend)

Create `.env` in your frontend project:

```bash
# Development
REACT_APP_BACKEND_URL=http://localhost:5000

# Production
# REACT_APP_BACKEND_URL=https://your-backend-domain.com
```

---

## 🧪 Step 5: Testing OAuth

### 5.1 Start Backend

```bash
cd sf_collab_backend_flask
python run.py
```

Backend should be running on `http://localhost:5000`

### 5.2 Test OAuth URLs Manually

**Test Google OAuth:**
```bash
# Open in browser
http://localhost:5000/api/auth/google/login
```

**Test GitHub OAuth:**
```bash
# Open in browser
http://localhost:5000/api/auth/github/login
```

### 5.3 What Should Happen

1. Browser redirects to Google/GitHub login
2. You authenticate
3. Redirects back to your callback URL
4. Page shows a script that posts message (or error if credentials missing)

### 5.4 Common Errors & Solutions

**Error: "redirect_uri_mismatch"**
- Solution: Add exact callback URL to OAuth app settings

**Error: "invalid_client"**
- Solution: Check CLIENT_ID and CLIENT_SECRET in `.env`

**Error: "401 Unauthorized"**
- Solution: OAuth credentials not loaded. Restart backend after adding to `.env`

**Error: "Origin not allowed"**
- Solution: Add frontend URL to CORS settings in `config.py`

---

## 🔒 Step 6: Security Considerations

### 6.1 Production Checklist

- [ ] Use HTTPS for all OAuth redirects
- [ ] Set secure environment variables
- [ ] Verify `event.origin` in frontend message handler
- [ ] Use proper CORS settings (whitelist specific domains)
- [ ] Don't expose OAuth secrets in frontend code
- [ ] Implement CSRF protection for regular auth
- [ ] Set secure cookie flags in production

### 6.2 Update CORS for Production

In `app/config.py`, ProductionConfig:

```python
# Set via environment variable
CORS_ORIGINS = os.getenv('CORS_ORIGINS', '').split(',')
```

In production `.env`:
```bash
CORS_ORIGINS=https://your-frontend.com,https://www.your-frontend.com
```

---

## 📱 Step 7: Mobile App Integration (Optional)

For mobile apps, you can't use popup windows. Instead:

1. Open system browser with OAuth URL
2. Implement deep linking to return to app
3. Or use redirect-based flow with custom URL schemes

Example OAuth URL with redirect:
```
http://localhost:5000/api/auth/google/login?redirect_to=myapp://oauth-callback
```

---

## 🔄 OAuth Response Format

### Success Response (postMessage)

```javascript
{
  type: 'oauth_success',
  provider: 'google' | 'github',
  access_token: 'jwt-access-token',
  refreshToken: 'jwt-refresh-token',
  user: {
    id: 123,
    email: 'user@example.com',
    firstName: 'John',
    lastName: 'Doe',
    // ... full user object
  },
  is_new_user: true | false
}
```

### Error Response (postMessage)

```javascript
{
  type: 'oauth_error',
  provider: 'google' | 'github',
  error: 'Error message'
}
```

---

## 🛠️ Troubleshooting

### Backend Logs

Check backend console for:
```
🔥 GOOGLE REDIRECT URI: http://localhost:5000/api/auth/google/callback
🔥 GITHUB REDIRECT URI: http://localhost:5000/api/auth/github/callback
```

### Test Backend OAuth Config

```python
# In Python console
import os
from dotenv import load_dotenv
load_dotenv()

print("Google ID:", os.getenv('GOOGLE_CLIENT_ID'))
print("GitHub ID:", os.getenv('GITHUB_CLIENT_ID'))
```

### Debug Frontend Message Listener

```javascript
window.addEventListener('message', (event) => {
  console.log('Received message:', event.data);
  console.log('From origin:', event.origin);
});
```

---

## 📝 Complete `.env` Template

```bash
# Flask
PORT=5000
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-here

# OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret

# Database
DATABASE_URL=mysql+pymysql://user:pass@localhost:3306/dbname

# Optional
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password

REDIS_URL=redis://localhost:6379/0
FLASK_ENV=development
```

---

## ✅ Quick Start Checklist

1. [ ] Create `.env` file from `.env.example`
2. [ ] Get Google OAuth credentials
3. [ ] Get GitHub OAuth credentials
4. [ ] Add credentials to `.env`
5. [ ] Restart backend server
6. [ ] Test OAuth URLs in browser
7. [ ] Implement frontend OAuth helper
8. [ ] Test full login flow
9. [ ] Verify tokens stored correctly
10. [ ] Test with new and existing users

---

## 🎯 Next Steps

After OAuth is working:
1. Implement email verification
2. Add password reset flow
3. Set up refresh token rotation
4. Add rate limiting to auth endpoints
5. Implement session management
6. Add audit logging for auth events

---

## 📞 Support

If you encounter issues:
1. Check backend console for errors
2. Check browser console for messages
3. Verify OAuth credentials are correct
4. Ensure callback URLs match exactly
5. Test with both new and existing users

---

**Last Updated:** December 2024
**Backend Version:** Flask + Authlib
**Supported Providers:** Google, GitHub
