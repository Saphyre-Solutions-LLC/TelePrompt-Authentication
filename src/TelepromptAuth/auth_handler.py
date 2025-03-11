import msal
import webbrowser
import threading
import time
import json
import os
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('azure_auth')

class TokenCache:
    def __init__(self, app_name):
        self.app_name = app_name
        self.cache_file = self._get_cache_path()
        self.encryption_key = self._generate_encryption_key()
        self.cipher = Fernet(self.encryption_key)
        
    def _get_cache_path(self):
        """Get platform-specific token cache location"""
        if os.name == 'nt':  # Windows
            base_dir = os.path.join(os.environ['LOCALAPPDATA'], self.app_name)
        elif os.name == 'posix':  # macOS/Linux
            base_dir = os.path.expanduser(f"~/.config/{self.app_name}")
        else:
            base_dir = os.path.expanduser(f"~/.{self.app_name}")
            
        # Ensure directory exists
        os.makedirs(base_dir, exist_ok=True)
        return os.path.join(base_dir, "token_cache.dat")
    
    def _generate_encryption_key(self):
        """Generate encryption key based on machine-specific info"""
        # In production, you might want to use a more sophisticated approach
        # This is a simplified approach that creates a key from machine ID + app name
        if os.name == 'nt':
            machine_id = os.environ.get('COMPUTERNAME', '')
        else:
            try:
                with open('/etc/machine-id', 'r') as f:
                    machine_id = f.read().strip()
            except:
                machine_id = os.uname().nodename
        
        # Derive a key using PBKDF2
        salt = b'azureb2cauth'  # You might want to store this securely
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive((machine_id + self.app_name).encode()))
        return key
    
    def save_token(self, token_data):
        """Encrypt and save token data"""
        try:
            encrypted_data = self.cipher.encrypt(json.dumps(token_data).encode())
            with open(self.cache_file, 'wb') as f:
                f.write(encrypted_data)
            logger.info("Token cached successfully")
            return True
        except Exception as e:
            logger.error(f"Error saving token: {str(e)}")
            return False
    
    def load_token(self):
        """Load and decrypt token data"""
        try:
            if not os.path.exists(self.cache_file):
                return None
                
            with open(self.cache_file, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = self.cipher.decrypt(encrypted_data)
            return json.loads(decrypted_data)
        except Exception as e:
            logger.error(f"Error loading token: {str(e)}")
            # If the file is corrupted, delete it
            try:
                os.remove(self.cache_file)
            except:
                pass
            return None

class AuthRedirectHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Send success response to browser
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        success_html = """
        <html>
        <head>
            <title>Authentication Complete</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    text-align: center;
                    margin-top: 50px;
                    background-color: #f0f0f0;
                }
                .container {
                    background-color: white;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    padding: 20px;
                    max-width: 500px;
                    margin: 0 auto;
                }
                .success {
                    color: #4CAF50;
                    font-size: 24px;
                }
                .error {
                    color: #F44336;
                    font-size: 24px;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1 class="success">Authentication Completed</h1>
                <p>You have successfully authenticated. You can close this window and return to the application.</p>
            </div>
            <script>
                setTimeout(function() {
                    window.close();
                }, 3000);
            </script>
        </body>
        </html>
        """
        
        error_html = """
        <html>
        <head>
            <title>Authentication Error</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    text-align: center;
                    margin-top: 50px;
                    background-color: #f0f0f0;
                }
                .container {
                    background-color: white;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    padding: 20px;
                    max-width: 500px;
                    margin: 0 auto;
                }
                .success {
                    color: #4CAF50;
                    font-size: 24px;
                }
                .error {
                    color: #F44336;
                    font-size: 24px;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1 class="error">Authentication Error</h1>
                <p>There was an error during authentication. Please try again.</p>
            </div>
        </body>
        </html>
        """
        
        # Extract auth code or error
        query = urlparse(self.path).query
        params = parse_qs(query)
        
        # Store the response
        self.server.auth_response = params
        self.server.response_received = True
        
        # Return appropriate HTML based on response
        if 'error' in params:
            self.wfile.write(error_html.encode())
        else:
            self.wfile.write(success_html.encode())
        
    def log_message(self, format, *args):
        # Suppress server logs
        return

class B2CAuthenticator:
    def __init__(self, client_id, tenant_name, policy_name, app_name, redirect_port=8000):
        self.client_id = client_id
        self.tenant_name = tenant_name
        self.policy_name = policy_name
        self.app_name = app_name
        self.redirect_port = redirect_port
        self.redirect_uri = f"http://localhost:{redirect_port}"
        
        # Authority for B2C
        self.authority = f"https://{tenant_name}.b2clogin.com/{tenant_name}.onmicrosoft.com/{policy_name}"
        
        # Initialize token cache
        self.token_cache = TokenCache(app_name)
        
        # Create MSAL app with token cache
        self.app = msal.PublicClientApplication(
            client_id=client_id,
            authority=self.authority
        )
        
    def _start_auth_server(self):
        """Start the authentication redirect server"""
        for attempt in range(3):  # Try a few ports if the default is taken
            try:
                port = self.redirect_port + attempt
                server = HTTPServer(('localhost', port), AuthRedirectHandler)
                self.redirect_uri = f"http://localhost:{port}"
                
                server.auth_response = None
                server.response_received = False
                
                server_thread = threading.Thread(target=server.serve_forever)
                server_thread.daemon = True
                server_thread.start()
                
                return server, server_thread
            except OSError:
                logger.warning(f"Port {port} is in use, trying another port")
                continue
        
        # If all attempts failed
        raise RuntimeError("Could not start authentication server. All ports are in use.")
    
    def get_token_silent(self, scopes):
        """Try to get token silently from cache"""
        accounts = self.app.get_accounts()
        if accounts:
            # Use the first account (usually there's just one)
            result = self.app.acquire_token_silent(scopes, account=accounts[0])
            return result
        return None
    
    def authenticate(self, scopes=None):
        """Authenticate user interactively or use cached token"""
        if scopes is None:
            scopes = ["openid", "profile", "offline_access"]
            
        # Try to get token silently first
        result = self.get_token_silent(scopes)
        if result:
            logger.info("Token acquired silently from cache")
            return result
        
        # If silent auth fails, we need interactive auth
        logger.info("Silent auth failed, starting interactive authentication")
        
        # Start local server for redirect
        try:
            server, server_thread = self._start_auth_server()
        except RuntimeError as e:
            logger.error(str(e))
            return None
        
        try:
            # Get auth URL with PKCE
            auth_url = self.app.get_authorization_request_url(
                scopes=scopes,
                redirect_uri=self.redirect_uri,
                prompt="login"
            )
            
            # Open browser
            logger.info(f"Opening browser for authentication: {auth_url}")
            webbrowser.open(auth_url)
            
            # Wait for response with timeout
            timeout = 300  # 5 minutes
            start_time = time.time()
            while not server.response_received and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            if not server.response_received:
                logger.error("Authentication timed out")
                return None
            
            # Process response
            if "error" in server.auth_response:
                error = server.auth_response["error"][0]
                error_desc = server.auth_response.get("error_description", ["Unknown error"])[0]
                logger.error(f"Authentication error: {error} - {error_desc}")
                return None
            
            if "code" in server.auth_response:
                auth_code = server.auth_response["code"][0]
                # Exchange code for tokens
                result = self.app.acquire_token_by_authorization_code(
                    code=auth_code,
                    scopes=scopes,
                    redirect_uri=self.redirect_uri
                )
                
                if "error" in result:
                    logger.error(f"Token acquisition failed: {result.get('error')} - {result.get('error_description')}")
                    return None
                
                # Save token to cache
                self.token_cache.save_token(result)
                
                return result
            
            logger.error("No code received in authentication response")
            return None
            
        except Exception as e:
            logger.exception("Authentication error")
            return None
        finally:
            # Cleanup
            server.shutdown()
            server_thread.join(timeout=5)
            server.server_close()
    
    def logout(self):
        """Clear token cache to log out user"""
        try:
            os.remove(self.token_cache.cache_file)
            logger.info("User logged out successfully")
            return True
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return False
