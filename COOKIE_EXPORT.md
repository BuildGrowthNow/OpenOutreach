# How to Export LinkedIn Cookies for OpenOutreach

⚠️ **Important**: The daemon needs the **full cookie set** from an authenticated LinkedIn session to work with the Voyager API, not just the `li_at` cookie.

LinkedIn's Voyager API requires multiple cookies including `li_at` (HttpOnly), `JSESSIONID`, CSRF tokens, and tracking cookies. Uploading only `li_at` or using incomplete exports will cause **401 Unauthorized** errors.

## Required: Browser Extension Method

Browser extensions can export HttpOnly cookies (including `li_at`). Browser console scripts using `document.cookie` **cannot** access HttpOnly cookies and will fail.

### Steps:

1. Install one of these extensions:
   - [**EditThisCookie**](https://chromewebstore.google.com/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg) (Chrome/Edge, 3M+ users)
   - [**Cookie-Editor**](https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm) (Chrome/Edge/Firefox, open source)

2. Log into LinkedIn at https://www.linkedin.com/feed/

3. Click the extension icon in your browser toolbar

4. Click "Export" → "JSON" (EditThisCookie) or the export icon (Cookie-Editor)

5. **Verify** the exported JSON includes the `li_at` cookie:
   ```json
   [
     ...
     {
       "name": "li_at",
       "value": "AQEDA...",
       "domain": ".www.linkedin.com",
       "httpOnly": true,
       ...
     },
     ...
   ]
   ```

6. Copy the entire JSON array (starts with `[`)

7. Go to Settings → LinkedIn Connection in OpenOutreach

8. Expand "Optional session cookie"

9. Paste the JSON array into the "Cookie JSON Array" field

10. Click "Add Credentials"

## Why Browser Console Scripts Don't Work

The `li_at` cookie has the `HttpOnly` flag, which prevents JavaScript (including browser console scripts) from accessing it. This is a security feature.

Only browser extensions with the proper permissions can export HttpOnly cookies.

## Security Note

Browser extensions can access all site data. Only install extensions from trusted publishers with good reviews. Both recommended extensions are well-established (millions of users / open source code).
