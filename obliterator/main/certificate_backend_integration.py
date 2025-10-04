#!/usr/bin/env python3
# certificate_backend_integration.py
# Module to send JSON certificates to the backend for PDF generation
# This is a standalone module that doesn't modify the main GUI

import json
import requests
import os
import time
from typing import Dict, Optional, Tuple
from datetime import datetime
import getpass

class SupabaseAuth:
    """Handle Supabase authentication"""
    
    def __init__(self, supabase_url: str, supabase_key: str):
        """Initialize Supabase auth client"""
        self.supabase_url = supabase_url.rstrip('/')
        self.supabase_key = supabase_key
        self.auth_token = None
        self.user_info = None
    
    def sign_in_with_password(self, email: str, password: str) -> Tuple[bool, Optional[str]]:
        """
        Sign in with email and password
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            auth_url = f"{self.supabase_url}/auth/v1/token?grant_type=password"
            headers = {
                'apikey': self.supabase_key,
                'Content-Type': 'application/json'
            }
            payload = {
                'email': email,
                'password': password
            }
            
            response = requests.post(auth_url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                auth_data = response.json()
                self.auth_token = auth_data.get('access_token')
                self.user_info = auth_data.get('user', {})
                print(f"✅ Successfully authenticated as: {self.user_info.get('email', 'Unknown')}")
                return True, None
            else:
                error_msg = response.json().get('error_description', f'Authentication failed: {response.status_code}')
                return False, error_msg
                
        except Exception as e:
            return False, str(e)
    
    def sign_up_with_password(self, email: str, password: str) -> Tuple[bool, Optional[str]]:
        """
        Sign up with email and password
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            signup_url = f"{self.supabase_url}/auth/v1/signup"
            headers = {
                'apikey': self.supabase_key,
                'Content-Type': 'application/json'
            }
            payload = {
                'email': email,
                'password': password
            }
            
            response = requests.post(signup_url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                auth_data = response.json()
                self.auth_token = auth_data.get('access_token')
                self.user_info = auth_data.get('user', {})
                print(f"✅ Successfully signed up and authenticated as: {self.user_info.get('email', 'Unknown')}")
                return True, None
            else:
                error_msg = response.json().get('error_description', f'Sign up failed: {response.status_code}')
                return False, error_msg
                
        except Exception as e:
            return False, str(e)
    
    def get_auth_headers(self) -> Dict[str, str]:
        """Get headers with authentication token"""
        if self.auth_token:
            return {
                'Authorization': f'Bearer {self.auth_token}',
                'apikey': self.supabase_key
            }
        return {'apikey': self.supabase_key}
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated"""
        return self.auth_token is not None


class CertificateBackendClient:
    """Client for interacting with the certificate PDF generation backend"""
    
    def __init__(self, backend_url: str = "https://obliterator-certificatebackend.onrender.com", auth_token: Optional[str] = None, 
                 supabase_auth: Optional[SupabaseAuth] = None):
        """
        Initialize the backend client
        
        Args:
            backend_url: Base URL of the backend server
            auth_token: Optional authentication token if backend requires auth
            supabase_auth: Optional Supabase authentication client
        """
        self.backend_url = backend_url.rstrip('/')
        self.auth_token = auth_token
        self.supabase_auth = supabase_auth
        
        self.headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'CertificateClient/1.0'
        }
        
        # Add authentication headers
        if supabase_auth and supabase_auth.is_authenticated():
            self.headers.update(supabase_auth.get_auth_headers())
            print(f"🔐 Using Supabase authentication for user: {supabase_auth.user_info.get('email', 'Unknown')}")
        elif auth_token:
            self.headers['Authorization'] = f'Bearer {auth_token}'
            print(f"🔐 Using provided auth token")
        
        # Set up session for connection reuse
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def test_connection(self) -> bool:
        """Test connection to the backend server"""
        try:
            print(f"Testing connection to: {self.backend_url}")
            
            # Try multiple common health check endpoints
            health_endpoints = ['/health', '/api/health', '/status', '/ping', '/']
            
            for endpoint in health_endpoints:
                try:
                    url = f"{self.backend_url}{endpoint}"
                    print(f"Trying: {url}")
                    response = self.session.get(url, timeout=10)
                    print(f"Response status: {response.status_code}")
                    
                    if response.status_code in [200, 404]:  # 404 might mean endpoint exists but wrong path
                        if response.status_code == 200:
                            print(f"✅ Health check successful at {endpoint}")
                        return True
                        
                except requests.exceptions.RequestException as e:
                    print(f"Failed {endpoint}: {e}")
                    continue
            
            # If no health endpoint works, try a simple GET to root
            response = self.session.get(self.backend_url, timeout=10)
            return response.status_code < 500  # Any response except server error
            
        except Exception as e:
            print(f"Backend connection test failed: {e}")
            return False
    
    # Enhanced convert_obliterator_to_sanitization_format method
    # Replace the existing method in certificate_backend_integration.py with this one
    
    def convert_obliterator_to_sanitization_format(self, obliterator_json: Dict) -> Dict:
        """
        Pass through the Obliterator JSON format directly - it's already in the correct format!
        """
        try:
            # Extract the certificate payload if it's wrapped
            if 'certificate_payload' in obliterator_json:
                return obliterator_json['certificate_payload']
            else:
                # It's already in the correct format
                return obliterator_json
                
        except Exception as e:
            print(f"❌ Error processing JSON: {e}")
            raise
    
    def generate_pdf_from_json(self, json_file_path: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Send JSON certificate to backend for PDF generation
        
        Args:
            json_file_path: Path to the JSON certificate file
            
        Returns:
            Tuple of (success, pdf_url, error_message)
        """
        try:
            print(f"📄 Reading JSON file: {json_file_path}")
            
            # Check if file exists
            if not os.path.exists(json_file_path):
                error_msg = f"JSON file not found: {json_file_path}"
                print(f"❌ {error_msg}")
                return False, None, error_msg
            
            # Read the JSON file
            with open(json_file_path, 'r', encoding='utf-8') as f:
                obliterator_json = json.load(f)
            
            print(f"✅ JSON loaded successfully")
            
            # Convert to backend format
            sanitization_data = self.convert_obliterator_to_sanitization_format(obliterator_json)
            
            # Try multiple possible endpoints for PDF generation
            endpoints = [
                '/generate-certificate',
                '/api/generate-certificate', 
                '/certificate/generate',
                '/api/certificate/generate',
                '/generate-pdf',
                '/api/generate-pdf'
            ]
            
            for endpoint in endpoints:
                try:
                    url = f"{self.backend_url}{endpoint}"
                    print(f"🚀 Trying PDF generation at: {url}")
                    
                    # Send to backend
                    response = self.session.post(
                        url,
                        json=sanitization_data,
                        timeout=60  # Increased timeout for PDF generation
                    )
                    
                    print(f"📡 Response status: {response.status_code}")
                    print(f"📡 Response headers: {dict(response.headers)}")
                    
                    if response.status_code == 200:
                        try:
                            result = response.json()
                            pdf_url = result.get('pdf_url') or result.get('url') or result.get('download_url')
                            
                            if pdf_url:
                                print(f"✅ PDF generated successfully: {pdf_url}")
                                return True, pdf_url, None
                            else:
                                print(f"⚠️  Success response but no PDF URL in: {result}")
                                # Maybe the PDF is returned directly as binary content
                                if response.headers.get('content-type', '').startswith('application/pdf'):
                                    print("📄 PDF returned as binary content")
                                    return True, None, None  # Success but no URL
                                
                        except json.JSONDecodeError:
                            print("⚠️  Response is not JSON, checking if it's PDF binary...")
                            if response.headers.get('content-type', '').startswith('application/pdf'):
                                print("📄 PDF returned as binary content")
                                return True, None, None
                            
                    elif response.status_code == 404:
                        print(f"⚠️  Endpoint not found: {endpoint}")
                        continue  # Try next endpoint
                    else:
                        error_msg = f"Backend returned {response.status_code}: {response.text[:500]}"
                        print(f"❌ {error_msg}")
                        # Don't return error yet, try other endpoints
                        
                except requests.exceptions.RequestException as e:
                    print(f"❌ Request failed for {endpoint}: {e}")
                    continue
            
            # If we get here, all endpoints failed
            error_msg = "All PDF generation endpoints failed"
            print(f"❌ {error_msg}")
            return False, None, error_msg
                
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(f"❌ Error generating PDF: {error_msg}")
            return False, None, error_msg
    
    def download_pdf(self, pdf_url: str, output_path: str) -> bool:
        """
        Download PDF from URL to local file
        
        Args:
            pdf_url: URL of the PDF to download
            output_path: Local path to save the PDF
            
        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"⬇️  Downloading PDF from: {pdf_url}")
            
            # Make sure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            response = self.session.get(pdf_url, timeout=60, stream=True)
            if response.status_code == 200:
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        
                print(f"✅ PDF downloaded to: {output_path}")
                return True
            else:
                print(f"❌ Failed to download PDF: {response.status_code} - {response.text[:200]}")
                return False
                
        except Exception as e:
            print(f"❌ Error downloading PDF: {e}")
            return False
    
    def batch_process_certificates(self, cert_dir: str, output_dir: str = None) -> Dict:
        """
        Process all JSON certificates in a directory
        
        Args:
            cert_dir: Directory containing JSON certificates
            output_dir: Directory to save PDFs (optional)
            
        Returns:
            Dictionary with processing results
        """
        if not os.path.exists(cert_dir):
            return {'error': f'Certificate directory not found: {cert_dir}'}
        
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        results = {
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'certificates': []
        }
        
        # Find all JSON certificate files
        json_files = [f for f in os.listdir(cert_dir) 
                     if f.endswith('.json') and os.path.isfile(os.path.join(cert_dir, f))]
        
        if not json_files:
            print(f"⚠️  No JSON files found in {cert_dir}")
            return results
        
        print(f"📁 Found {len(json_files)} JSON files to process")
        
        for json_file in json_files:
            json_path = os.path.join(cert_dir, json_file)
            print(f"\n{'='*60}")
            print(f"📄 Processing: {json_file}")
            print(f"{'='*60}")
            
            success, pdf_url, error = self.generate_pdf_from_json(json_path)
            
            cert_result = {
                'json_file': json_file,
                'json_path': json_path,
                'success': success,
                'pdf_url': pdf_url,
                'error': error
            }
            
            if success and pdf_url and output_dir:
                # Download the PDF locally
                pdf_filename = json_file.replace('.json', '.pdf')
                pdf_path = os.path.join(output_dir, pdf_filename)
                if self.download_pdf(pdf_url, pdf_path):
                    cert_result['local_pdf_path'] = pdf_path
            
            results['certificates'].append(cert_result)
            results['processed'] += 1
            
            if success:
                results['successful'] += 1
                print(f"✅ Success: {json_file}")
            else:
                results['failed'] += 1
                print(f"❌ Failed: {json_file} - {error}")
            
            # Small delay to avoid overwhelming the server
            time.sleep(1)
        
        return results
    
    def __del__(self):
        """Clean up the session"""
        if hasattr(self, 'session'):
            self.session.close()


def authenticate_user(supabase_url: str, supabase_key: str) -> Optional[SupabaseAuth]:
    """
    Interactive authentication with Supabase
    
    Returns:
        SupabaseAuth instance if successful, None otherwise
    """
    auth_client = SupabaseAuth(supabase_url, supabase_key)
    
    print(f"\n🔐 Authentication Required")
    print(f"Supabase URL: {supabase_url}")
    print(f"Choose authentication method:")
    print(f"1. Sign in with existing account")
    print(f"2. Create new account")
    
    while True:
        choice = input("Enter choice (1 or 2): ").strip()
        if choice in ['1', '2']:
            break
        print("Please enter 1 or 2")
    
    email = input("Enter email: ").strip()
    password = getpass.getpass("Enter password: ")
    
    if choice == '1':
        success, error = auth_client.sign_in_with_password(email, password)
        if not success:
            print(f"❌ Sign in failed: {error}")
            return None
    else:
        success, error = auth_client.sign_up_with_password(email, password)
        if not success:
            print(f"❌ Sign up failed: {error}")
            return None
    
    return auth_client


# Standalone script functionality
if __name__ == "__main__":
    import argparse
    
    # Default Supabase configuration
    DEFAULT_SUPABASE_URL = "https://ajqmxtjlxplnbofwoxtf.supabase.co"
    DEFAULT_SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFqcW14dGpseHBsbmJvZndveHRmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTgzNzMzMjEsImV4cCI6MjA3Mzk0OTMyMX0.m9C9chwlriwRojINYQrWSo96wyJTKOQONkqsi8-xsBQ"
    
    parser = argparse.ArgumentParser(description='Generate PDF certificates from JSON')
    parser.add_argument('--backend-url', default='https://obliterator-certificatebackend.onrender.com',
                       help='Backend server URL')
    parser.add_argument('--auth-token', help='Authentication token if required')
    parser.add_argument('--cert-dir', default='./certificates',
                       help='Directory containing JSON certificates')
    parser.add_argument('--output-dir', help='Directory to save PDF files')
    parser.add_argument('--single-file', help='Process a single JSON file')
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='Enable verbose logging')
    parser.add_argument('--supabase-url', default=DEFAULT_SUPABASE_URL,
                       help='Supabase URL for authentication')
    parser.add_argument('--supabase-key', default=DEFAULT_SUPABASE_KEY,
                       help='Supabase anon key for authentication')
    parser.add_argument('--no-auth', action='store_true',
                       help='Skip authentication (use for testing)')
    parser.add_argument('--email', help='Email for automatic authentication')
    parser.add_argument('--password', help='Password for automatic authentication')
    
    args = parser.parse_args()
    
    # Initialize authentication if not disabled
    supabase_auth = None
    if not args.no_auth:
        if args.email and args.password:
            # Automatic authentication
            print(f"🔐 Authenticating with provided credentials...")
            supabase_auth = SupabaseAuth(args.supabase_url, args.supabase_key)
            success, error = supabase_auth.sign_in_with_password(args.email, args.password)
            if not success:
                print(f"❌ Authentication failed: {error}")
                # Try to create account
                print(f"🔄 Trying to create new account...")
                success, error = supabase_auth.sign_up_with_password(args.email, args.password)
                if not success:
                    print(f"❌ Account creation failed: {error}")
                    exit(1)
        else:
            # Interactive authentication
            supabase_auth = authenticate_user(args.supabase_url, args.supabase_key)
            if not supabase_auth:
                print("❌ Authentication required. Exiting.")
                exit(1)
    else:
        print("⚠️  Authentication skipped (--no-auth flag used)")
    
    # Initialize client
    print(f"\n🚀 Initializing Certificate Backend Client")
    print(f"Backend URL: {args.backend_url}")
    
    client = CertificateBackendClient(args.backend_url, args.auth_token, supabase_auth)
    
    # Test connection
    print(f"\n🔌 Testing connection to backend...")
    if not client.test_connection():
        print("❌ Cannot connect to backend server.")
        print("💡 Troubleshooting tips:")
        print("   - Check if the backend server is running")
        print("   - Verify the URL is correct")
        print("   - Check firewall/network settings")
        print(f"   - Try: curl -I {args.backend_url}")
        exit(1)
    print("✅ Backend connection successful!")
    
    if args.single_file:
        # Process single file
        print(f"\n📄 Processing single file: {args.single_file}")
        
        if not os.path.exists(args.single_file):
            print(f"❌ File not found: {args.single_file}")
            exit(1)
            
        success, pdf_url, error = client.generate_pdf_from_json(args.single_file)
        if success:
            if pdf_url:
                print(f"✅ PDF URL: {pdf_url}")
                if args.output_dir:
                    if not os.path.exists(args.output_dir):
                        os.makedirs(args.output_dir)
                    pdf_filename = os.path.basename(args.single_file).replace('.json', '.pdf')
                    pdf_path = os.path.join(args.output_dir, pdf_filename)
                    client.download_pdf(pdf_url, pdf_path)
            else:
                print("✅ PDF generated successfully (no URL returned)")
        else:
            print(f"❌ Failed: {error}")
            exit(1)
    else:
        # Batch process directory
        print(f"\n📁 Processing certificates in: {args.cert_dir}")
        
        if not os.path.exists(args.cert_dir):
            print(f"❌ Certificate directory not found: {args.cert_dir}")
            exit(1)
            
        results = client.batch_process_certificates(args.cert_dir, args.output_dir)
        
        if 'error' in results:
            print(f"❌ Error: {results['error']}")
            exit(1)
        
        print(f"\n{'='*60}")
        print(f"📊 PROCESSING COMPLETE!")
        print(f"{'='*60}")
        print(f"Total Processed: {results['processed']}")
        print(f"Successful: {results['successful']}")
        print(f"Failed: {results['failed']}")
        
        if results['successful'] > 0:
            print(f"\n✅ Successful certificates:")
            for cert in results['certificates']:
                if cert['success']:
                    local_path = cert.get('local_pdf_path', 'N/A')
                    print(f"  - {cert['json_file']} → {local_path}")
        
        if results['failed'] > 0:
            print(f"\n❌ Failed certificates:")
            for cert in results['certificates']:
                if not cert['success']:
                    print(f"  - {cert['json_file']}: {cert['error']}")
            exit(1)
    
    print(f"\n🎉 All done!")
