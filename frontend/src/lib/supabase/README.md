# Supabase Authentication Integration for OpenOutreach

This directory contains the Supabase authentication integration for the OpenOutreach application.

## Architecture

The authentication system uses:

1. **Supabase** - As the canonical identity provider (signup, signin, signout, email verification)
2. **Next.js** - For the frontend UI and state management
3. **Django REST Framework** - For the backend API with Supabase JWT validation

## Files

- `client.ts` - Supabase client configuration and initialization
- `index.ts` - Centralized exports for Supabase functionality
- `types.ts` - TypeScript type definitions

## Setup

### 1. Create a Supabase Project

1. Go to [Supabase](https://supabase.com/)
2. Create a new project
3. Get your project URL and API keys from project settings

### 2. Configure Environment Variables

Add to `frontend/.env.local`:
```bash
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key-here
```

### 3. Database Setup

The Supabase authentication system uses a `user_profiles` table to store user metadata:

```sql
create table user_profiles (
  id uuid references auth.users not null,
  full_name text,
  avatar_url text,
  created_at timestamp with time zone default timezone('utc'::text, now()),
  primary key (id)
);

-- Enable Row Level Security
alter table user_profiles enable row level security;

-- Policies
create policy "Users can view own profile"
  on user_profiles for select
  using ( auth.uid() = id );

create policy "Users can update own profile"
  on user_profiles for update
  using ( auth.uid() = id );
```

## Usage

### Client-Side Authentication

```typescript
import { supabase, isSignedIn, getCurrentUser, signOutUser } from '@/lib/supabase'

// Check if user is signed in
const signedIn = await isSignedIn()

// Get current user
const user = await getCurrentUser()

// Sign out
await signOutUser()
```

### Authentication Store

The Zustand auth store (`authStore.ts`) manages authentication state:

```typescript
import { useAuthStore } from '@/lib/authStore'

const { 
  user, 
  isAuthenticated, 
  isLoading,
  login, 
  signup, 
  logout 
} = useAuthStore()
```

### Auth Provider

The `AuthProvider` component wraps the application and provides authentication context:

```tsx
import { AuthProvider } from '@/app/auth-provider'

export default function RootLayout({ children }) {
  return (
    <html>
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  )
}
```

## Authentication Flow

1. User visits the application
2. AuthProvider initializes Supabase client
3. User clicks "Sign Up" or "Login"
4. User fills in credentials (email/password)
5. AuthStore calls Supabase authentication methods
6. On success, user is redirected to dashboard
7. On each request, JWT is sent to backend for validation

## Backend Integration

The Django backend validates Supabase JWT tokens on each request:

```python
from openoutreach.api.authentication import SupabaseJWTAuthentication

# In your views
@authentication_classes([SupabaseJWTAuthentication])
@permission_classes([IsAuthenticated])
class MyView(APIView):
    def get(self, request):
        # request.user is authenticated via Supabase JWT
        pass
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL | Yes |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon/public key | Yes |
| `SUPABASE_SERVICE_KEY` | Supabase service key (server-side) | No |

## Error Handling

The auth store and Supabase client handle authentication errors gracefully. Common errors include:

- `invalid credentials` - Login failed due to invalid credentials
- `email not verified` - User must verify email before signing in
- `network error` - Connection to Supabase failed

## Security

1. **Never expose the service key** - The service key should only be used server-side
2. **Enable Row Level Security (RLS)** - Protect data at the database level
3. **Use HTTPS in production** - Ensure all traffic is encrypted
4. **Enable account enumeration prevention** - Configure in Supabase dashboard

## Testing

To test the authentication flow:

1. Start the development servers
2. Visit the signup page
3. Create a new account
4. Verify email (if email verification is enabled)
5. Sign in with credentials
6. Verify dashboard access

## Troubleshooting

### Common Issues

1. **"SUPABASE_URL not configured"**
   - Ensure `NEXT_PUBLIC_SUPABASE_URL` is set in `.env.local`
   - Restart the development server after Env changes

2. **"Invalid credentials"**
   - Check that email/password are correct
   - Verify email if required in Supabase settings

3. **"Network error"**
   - Check Supabase project URL
   - Verify API keys are correct

## Next Steps

- Implement email verification flow
- Add password reset functionality
- Configure Supabase dashboard settings
- Set up production deployment