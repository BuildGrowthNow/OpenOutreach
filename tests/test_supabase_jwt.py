"""
Test script to diagnose Supabase JWT authentication issues.

Usage:
    python tests/test_supabase_jwt.py
"""

import os
import sys
import jwt
import json
import requests
from datetime import datetime

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Load environment variables from .env
env_file = os.path.join(project_root, '.env')
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())

import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def decode_jwt_without_verify(token):
    """Decode JWT token without verification to get payload."""
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload
    except jwt.PyJWTError as e:
        logger.error(f"Failed to decode token without verification: {e}")
        return None


def verify_token_with_hs256(token, secret_key, key_name="SERVICE"):
    """Try to verify token with HS256 algorithm."""
    try:
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
        logger.info(f"✓ Token verified with HS256 using {key_name} key!")
        return payload, "HS256"
    except jwt.PyJWTError as e:
        logger.error(f"✗ HS256 verification with {key_name} key failed: {e}")
        return None, None


def verify_token_with_rs256(token, jwks_uri):
    """Try to verify token with RS256 using JWKS."""
    try:
        jwks_response = requests.get(jwks_uri, timeout=5)
        jwks = jwks_response.json()
        
        # Get header to find the key ID
        header = jwt.get_unverified_header(token)
        kid = header.get('kid')
        
        if not kid:
            logger.error("No key ID found in token header")
            return None, None
        
        # Find the key in JWKS
        rsa_key = None
        for key in jwks.get('keys', []):
            if key.get('kid') == kid:
                rsa_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
                break
        
        if not rsa_key:
            logger.error("No matching key found in JWKS")
            return None, None
        
        payload = jwt.decode(token, rsa_key, algorithms=["RS256"])
        logger.info("✓ Token verified with RS256!")
        return payload, "RS256"
    except Exception as e:
        logger.error(f"✗ RS256 verification failed: {e}")
        return None, None


def test_environment_configuration():
    """Test if environment is properly configured."""
    print("\n" + "="*60)
    print("ENVIRONMENT CONFIGURATION TEST")
    print("="*60)
    
    required_vars = [
        'SUPABASE_URL',
        'SUPABASE_ANON_KEY', 
        'SUPABASE_SERVICE_KEY'
    ]
    
    all_set = True
    for var in required_vars:
        value = os.environ.get(var)
        if value:
            # Mask part of the key for security
            masked = value[:20] + '...' if len(value) > 20 else '***'
            logger.info(f"✓ {var} is set ({masked})")
        else:
            logger.error(f"✗ {var} is NOT set")
            all_set = False
    
    return all_set


def verify_token(token):
    """Helper function to verify a specific token."""
    print("\n" + "="*60)
    print(f"VERIFYING TOKEN: {token[:50]}...")
    print("="*60)
    
    # Decode without verification
    payload = decode_jwt_without_verify(token)
    if payload:
        print("\n--- Token Payload (decoded without verification) ---")
        print(json.dumps({
            'sub': payload.get('sub'),
            'email': payload.get('email'),
            'iat': payload.get('iat'),
            'exp': payload.get('exp'),
            'iss': payload.get('iss'),
            'role': payload.get('role'),
            'app_metadata': payload.get('app_metadata'),
            'user_metadata': payload.get('user_metadata'),
        }, indent=2))
        
        # Check algorithm from header
        header = jwt.get_unverified_header(token)
        print(f"\nToken Header: {json.dumps(header, indent=2)}")
        
        service_key = os.environ.get('SUPABASE_SERVICE_KEY')
        if service_key:
            print("\n--- Attempting verification with SERVICE key ---")
            verify_token_with_hs256(token, service_key, "SERVICE")
            
            # Also try with anon key if different
            anon_key = os.environ.get('SUPABASE_ANON_KEY')
            if anon_key and anon_key != service_key:
                print("\n--- Trying with ANON key ---")
                verify_token_with_hs256(token, anon_key, "ANON")
        
        # Check JWKS endpoint for RS256
        supabase_url = os.environ.get('SUPABASE_URL')
        if supabase_url:
            jwks_uri = f"{supabase_url}/rest/v1/jwks"
            print(f"\n--- Attempting RS256 verification via JWKS ---")
            print(f"JWKS URI: {jwks_uri}")
            verify_token_with_rs256(token, jwks_uri)
    
    return payload


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("SUPABASE JWT AUTHENTICATION DIAGNOSTIC TEST")
    print("="*60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Python: {sys.version}")
    
    # Test environment setup
    env_ok = test_environment_configuration()
    
    if not env_ok:
        print("\n❌ FAILED: Environment not properly configured")
        print("\nPlease fix the missing environment variables above.")
        return False
    
    print("\n✓ Environment configuration OK")
    
    # Show JWT library info
    print("\n" + "="*60)
    print("JWT LIBRARY INFO")
    print("="*60)
    logger.info(f"PyJWT version: {jwt.__version__}")
    
    print("\n" + "="*60)
    print("INSTRUCTIONS")
    print("="*60)
    print("""
1. Open your browser's Developer Tools (F12)
2. Go to Application tab → Local Storage
3. Look for 'sb-rubkyujjlgvizrwxddug-auth-token'
4. Copy the token value
5. Run: python tests/test_supabase_jwt.py
6. When prompted, paste your token to verify it

Alternatively, you can test directly:
from tests.test_supabase_jwt import verify_token
verify_token("YOUR_TOKEN_HERE")
    """)
    
    # Ask for token to test
    print("\n" + "="*60)
    print("TEST TOKEN VERIFICATION")
    print("="*60)
    
    token = input("\nEnter a Supabase JWT token to verify (or press Enter to skip): ").strip()
    if token:
        verify_token(token)
    
    print("\nDiagnostic test complete!")
    return True


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)