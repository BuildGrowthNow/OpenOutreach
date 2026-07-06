# How to Export LinkedIn Cookies for OpenOutreach

The daemon needs the **full cookie set** from an authenticated LinkedIn session to work with the Voyager API, not just the `li_at` cookie.

## Option 1: Browser Console (Recommended)

1. Log into LinkedIn in your browser
2. Navigate to https://www.linkedin.com/feed/
3. Open DevTools (F12)
4. Go to the Console tab
5. Paste this script and press Enter:

```javascript
copy(JSON.stringify({
  cookies: document.cookie.split('; ').map(c => {
    const [name, value] = c.split('=');
    return {
      name,
      value,
      domain: '.linkedin.com',
      path: '/',
      expires: -1,
      httpOnly: false,
      secure: true,
      sameSite: 'Lax'
    };
  })
}, null, 2));
console.log('Copied! Paste this JSON into the cookie field in Settings → LinkedIn Connection');
```

6. The full cookie JSON is now in your clipboard
7. Go to Settings → LinkedIn Connection in OpenOutreach
8. Paste the entire JSON into the "Optional Cookie" field
9. Click "Add Credentials"

## Option 2: Browser Extension

Use a cookie export extension like:
- **EditThisCookie** (Chrome/Edge): Export cookies for linkedin.com as JSON
- **Cookie-Editor** (Firefox): Export all cookies for linkedin.com

Then paste the exported JSON into the OpenOutreach cookie field.

## Why Just `li_at` Doesn't Work

LinkedIn's Voyager API requires multiple cookies including:
- `li_at` (authentication)
- `JSESSIONID` (session management)
- CSRF tokens
- Tracking cookies

Uploading only `li_at` allows the browser to load pages but API calls return 401 Unauthorized.
