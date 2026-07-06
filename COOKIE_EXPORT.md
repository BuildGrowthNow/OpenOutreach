# How to Export LinkedIn Cookies for OpenOutreach

⚠️ **Important**: The daemon needs the **full cookie set** from an authenticated LinkedIn session to work with the Voyager API, not just the `li_at` cookie.

LinkedIn's Voyager API requires multiple cookies including `li_at`, `JSESSIONID`, CSRF tokens, and tracking cookies. Uploading only `li_at` allows the browser to load pages but API calls return **401 Unauthorized**.

## Option 1: Browser Extension (Recommended)

Use a trusted cookie exporter to get ALL LinkedIn cookies as JSON:

1. Install one of these Chrome extensions:
   - [**EditThisCookie**](https://chromewebstore.google.com/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg) (most popular, 3M+ users)
   - [**Cookie-Editor**](https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm) (open source)

2. Log into LinkedIn at https://www.linkedin.com/feed/
3. Click the extension icon in your browser toolbar
4. Click "Export" → "JSON" (or similar button depending on extension)
5. Go to Settings → LinkedIn Connection in OpenOutreach
6. Paste the exported JSON into the "Full Cookie JSON" field
7. Click "Add Credentials"

## Option 2: Browser Console Script

No extension needed, but limited to non-HttpOnly cookies:

1. Log into LinkedIn at https://www.linkedin.com/feed/
2. Open DevTools (F12) → Console tab
3. Paste this script and press Enter:

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
console.log('✓ Copied to clipboard! Paste this into the cookie field in Settings → LinkedIn Connection');
```

4. The JSON is now in your clipboard
5. Go to Settings → LinkedIn Connection in OpenOutreach
6. Paste the JSON into the "Full Cookie JSON" field
7. Click "Add Credentials"

**Note**: This method misses HttpOnly cookies. Use Option 1 (browser extension) for the most complete export.

## Security Note

Browser extensions can access all site data. Only install extensions from trusted publishers with good reviews. Both recommended extensions are well-established (millions of users / open source).
