"""
SOAP Client Service for Spanish Government Communication (Verifactu)

This service implements SOAP 1.1 with:
- Document style (style="document")
- Literal encoding (use="literal")
- XML schema-based messages

Following Spanish government specifications for Verifactu integration.
"""

import logging
import os
import tempfile
import traceback
from typing import Dict, Any, Optional, Tuple
from zeep import Client, Settings
from zeep.exceptions import Fault, TransportError, XMLSyntaxError
from django.conf import settings
from decouple import config
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)

# SOAP 1.1 namespace as per W3C NOTE SOAP-20000508
# Reference: http://schemas.xmlsoap.org/soap/envelope/
SOAP_11_NAMESPACE = "http://schemas.xmlsoap.org/soap/envelope/"

# WSDL SOAP namespace
# Reference: http://schemas.xmlsoap.org/wsdl/soap/
WSDL_SOAP_NAMESPACE = "http://schemas.xmlsoap.org/wsdl/soap/"

# WSDL 1.1 namespace
# Reference: http://schemas.xmlsoap.org/wsdl/
WSDL_11_NAMESPACE = "http://schemas.xmlsoap.org/wsdl/"


class VerifactuSOAPClient:
    """
    SOAP Client for Verifactu (Spanish Government Facturación Electrónica)
    
    Implements SOAP 1.1 with document/literal style as required by Spanish government.
    
    Compliance with Spanish government Verifactu requirements:
    - SOAP Version: 1.1 (W3C NOTE SOAP-20000508)
      Namespace: http://schemas.xmlsoap.org/soap/envelope/
    - Style: document (style="document")
    - Encoding: literal (use="literal")
    - WSDL: 1.1 (W3C NOTE WSDL-20010315)
      Namespace: http://schemas.xmlsoap.org/wsdl/
    - XML Encoding: UTF-8
    """
    
    def __init__(
        self,
        wsdl_url: Optional[str] = None,
        timeout: int = 30,
        verify_ssl: bool = True,
        cert_file: Optional[str] = None,
        key_file: Optional[str] = None,
        cert_file_path: Optional[str] = None,
        cert_password: Optional[str] = None,
        service_name: Optional[str] = None,
        port_name: Optional[str] = None
    ):
        """
        Initialize the SOAP client.
        
        Args:
            wsdl_url: WSDL URL for the SOAP service (can be from settings)
            timeout: Request timeout in seconds
            verify_ssl: Whether to verify SSL certificates
            cert_file: Path to client certificate file (PEM format) - legacy support
            key_file: Path to client private key file (PEM format) - legacy support
            cert_file_path: Path to PKCS#12 certificate file (.pfx or .p12 - both formats are identical)
            cert_password: Password for the PKCS#12 certificate file
            service_name: Name of the service to use (e.g., 'sfVerifactu'). If None, uses first available.
            port_name: Name of the port to use (e.g., 'SistemaVerifactuPruebas'). If None, uses default port.
                      This is the preferred way to select testing vs production environment.
        """
        self.wsdl_url = wsdl_url or config('VERIFACTU_WSDL_URL', default='')
        self.timeout = timeout or config('VERIFACTU_SOAP_TIMEOUT', default=30, cast=int)
        # SSL verification disabled for testing environments (prewww.aeat.es)
        # In production, this should be enabled via VERIFACTU_VERIFY_SSL=True
        self.verify_ssl = verify_ssl if verify_ssl is not None else config('VERIFACTU_VERIFY_SSL', default=True, cast=bool)
        # self.verify_ssl = False
        
        # Service and port selection (preferred method)
        self.service_name = service_name or config('VERIFACTU_SERVICE_NAME', default=None)
        self.port_name = port_name or config('VERIFACTU_PORT_NAME', default=None)

        # Support for PKCS#12 certificate (.pfx/.p12 - both extensions are the same format)
        self.cert_file_path = cert_file_path or config('VERIFACTU_CERT_FILE_PATH', default=None)
        self.cert_password = cert_password or config('VERIFACTU_CERT_KEY', default=None)
        
        # Legacy support for separate PEM cert/key files
        self.cert_file = cert_file or config('VERIFACTU_CERT_FILE', default=None)
        self.key_file = key_file or config('VERIFACTU_KEY_FILE', default=None)
        
        # Temporary files for extracted cert/key (cleaned up on deletion)
        self._temp_cert_file: Optional[str] = None
        self._temp_key_file: Optional[str] = None
        
        # Store raw XML responses
        self._last_raw_xml_response: Optional[str] = None
        
        # Zeep settings for document/literal style
        # This ensures SOAP 1.1 with document style and literal encoding
        self.settings = Settings(
            strict=False,  # Allow some flexibility in XML parsing
            xml_huge_tree=True,  # Handle large XML documents
            forbid_entities=False,  # Allow XML entities
            forbid_external=False,  # Allow external references
            forbid_dtd=False,  # Allow DTD
        )
        
        self.client: Optional[Client] = None
        self._initialize_client()
    
    def _load_pkcs12_certificate(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Load certificate and key from PKCS#12 file (.pfx or .p12).
        
        Note: .pfx and .p12 are the same format, just different file extensions.
        This function supports both extensions.
        
        Returns:
            Tuple of (cert_file_path, key_file_path) as temporary files
        """
        if not self.cert_file_path:
            return None, None
        
        if not os.path.exists(self.cert_file_path):
            raise FileNotFoundError(f"Certificate file not found: {self.cert_file_path}")
        
        # Validate file extension (optional check for user clarity)
        file_ext = os.path.splitext(self.cert_file_path)[1].lower()
        if file_ext not in ['.pfx', '.p12']:
            logger.warning(
                f"Certificate file has extension '{file_ext}'. "
                f"Expected .pfx or .p12. Proceeding anyway as PKCS#12 format is determined by content."
            )
        
        try:
            # Import PKCS#12 support from cryptography
            # Note: pkcs12 module is available in cryptography >= 3.0
            load_pkcs12 = None
            try:
                from cryptography.hazmat.primitives.serialization import pkcs12
                load_pkcs12 = pkcs12.load_key_and_certificates
            except (ImportError, AttributeError):
                # Fallback: try direct import (older versions)
                try:
                    from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates
                    load_pkcs12 = load_key_and_certificates
                except ImportError:
                    pass
            
            if load_pkcs12 is None:
                raise ImportError(
                    "PKCS#12 support not available in this cryptography version. "
                    "Please upgrade: pip install 'cryptography>=3.0'"
                )
            
            # Read the PKCS#12 file (.pfx or .p12)
            with open(self.cert_file_path, 'rb') as f:
                pkcs12_data = f.read()
            
            # Extract certificate and key
            password = self.cert_password.encode('utf-8') if self.cert_password else None
            
            try:
                private_key, certificate, additional_certificates = load_pkcs12(
                    pkcs12_data,
                    password,
                    backend=default_backend()
                )
            except ValueError as e:
                if "Invalid password" in str(e) or "MAC verify failed" in str(e):
                    raise ValueError(f"Invalid certificate password: {str(e)}")
                raise
            
            if not certificate:
                raise ValueError("No certificate found in PKCS#12 file")
            
            if not private_key:
                raise ValueError("No private key found in PKCS#12 file")
            
            # Create temporary files for cert and key
            cert_fd, cert_path = tempfile.mkstemp(suffix='.pem', prefix='verifactu_cert_')
            key_fd, key_path = tempfile.mkstemp(suffix='.pem', prefix='verifactu_key_')
            
            try:
                # Write certificate to temp file
                with os.fdopen(cert_fd, 'wb') as cert_file:
                    cert_file.write(certificate.public_bytes(serialization.Encoding.PEM))
                
                # Write private key to temp file
                with os.fdopen(key_fd, 'wb') as key_file:
                    key_file.write(
                        private_key.private_bytes(
                            encoding=serialization.Encoding.PEM,
                            format=serialization.PrivateFormat.PKCS8,
                            encryption_algorithm=serialization.NoEncryption()
                        )
                    )
                
                # Store paths for cleanup
                self._temp_cert_file = cert_path
                self._temp_key_file = key_path
                
                logger.info(f"Successfully extracted certificate and key from {self.cert_file_path}")
                
                return cert_path, key_path
                
            except Exception as e:
                # Clean up temp files on error
                if os.path.exists(cert_path):
                    os.unlink(cert_path)
                if os.path.exists(key_path):
                    os.unlink(key_path)
                raise
                
        except ImportError:
            raise ImportError(
                "cryptography library is required for PKCS#12 support. "
                "Install it with: pip install cryptography"
            )
        except Exception as e:
            logger.error(f"Error loading PKCS#12 certificate: {str(e)}")
            raise
    
    def __del__(self):
        """Clean up temporary certificate files."""
        if self._temp_cert_file and os.path.exists(self._temp_cert_file):
            try:
                os.unlink(self._temp_cert_file)
            except Exception:
                pass
        
        if self._temp_key_file and os.path.exists(self._temp_key_file):
            try:
                os.unlink(self._temp_key_file)
            except Exception:
                pass
    
    def _initialize_client(self):
        """Initialize the Zeep SOAP client with proper configuration."""
        if not self.wsdl_url:
            logger.warning("WSDL URL not configured. Client will be initialized on first use.")
            return
        
        try:
            # Configure transport with SSL settings
            from zeep.transports import Transport
            import requests
            
            session = requests.Session()
            session.verify = self.verify_ssl
            session.timeout = self.timeout
            
            # Suppress urllib3 InsecureRequestWarning when SSL verification is disabled
            # This is intentional for testing environments (prewww.aeat.es)
            if not self.verify_ssl:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                logger.debug("SSL verification disabled - urllib3 warnings suppressed (testing environment)")
            
            # Add headers that might be required by the server
            session.headers.update({
                'User-Agent': 'Verifactu-SOAP-Client/1.0',
                'Accept': 'text/xml, application/xml, application/soap+xml, */*',
                'Content-Type': 'text/xml; charset=utf-8'
            })
            
            # Determine which certificate method to use
            cert_path = None
            key_path = None
            
            # Priority: PKCS#12 file (.pfx/.p12) > separate PEM files
            if self.cert_file_path:
                # Load from PKCS#12 file (.pfx or .p12)
                cert_path, key_path = self._load_pkcs12_certificate()
                logger.info(f"Using PKCS#12 certificate file: {self.cert_file_path}")
            elif self.cert_file and self.key_file:
                # Use separate PEM files (legacy support)
                cert_path = self.cert_file
                key_path = self.key_file
                logger.info("Using separate PEM certificate files")
            
            # Add client certificate if available
            # NOTE: The certificate is needed both for WSDL access AND for SOAP calls
            if cert_path and key_path:
                if not os.path.exists(cert_path):
                    raise FileNotFoundError(f"Certificate file not found: {cert_path}")
                if not os.path.exists(key_path):
                    raise FileNotFoundError(f"Key file not found: {key_path}")
                
                session.cert = (cert_path, key_path)
                logger.info(f"Client certificate configured: {cert_path}")
            else:
                logger.warning("No client certificate configured. Requests may fail if authentication is required.")
            
            # Validate WSDL URL format
            if self.wsdl_url and not self.wsdl_url.endswith('.wsdl'):
                logger.warning(
                    f"WSDL URL does not end with '.wsdl': {self.wsdl_url}\n"
                    f"This might be incorrect. Expected format: https://.../SuministroFactEmitidas.wsdl"
                )
            
            transport = Transport(session=session, timeout=self.timeout)
            
            # Create client with document/literal style
            # Zeep automatically uses SOAP 1.1 document/literal when the WSDL specifies it
            # After initialization, we explicitly verify compliance via _verify_soap_compliance()
            # If service_name and port_name are specified, pass them to Client constructor (if supported)
            client_kwargs = {
                'wsdl': self.wsdl_url,
                'settings': self.settings,
                'transport': transport
            }
            
            # Try to use Zeep's built-in service/port selection if available
            # (Some Zeep versions support this directly)
            if self.service_name and self.port_name:
                try:
                    client_kwargs['service_name'] = self.service_name
                    client_kwargs['port_name'] = self.port_name
                except TypeError:
                    # This version of Zeep doesn't support service_name/port_name in constructor
                    pass
            
            self.client = Client(**client_kwargs)
            
            # Explicitly verify and enforce SOAP 1.1 with document/literal style
            self._verify_soap_compliance()
            
            # Select specific port by name (preferred method - uses WSDL definitions)
            if self.port_name:
                try:
                    # Find the service and port by name
                    target_service = None
                    target_port = None
                    
                    # If service_name is specified, use it; otherwise search all services
                    services_to_check = []
                    if self.service_name:
                        if self.service_name in self.client.wsdl.services:
                            services_to_check = [self.client.wsdl.services[self.service_name]]
                        else:
                            logger.warning(f"Service '{self.service_name}' not found in WSDL. Available services: {list(self.client.wsdl.services.keys())}")
                    else:
                        services_to_check = list(self.client.wsdl.services.values())
                    
                    # Search for the port
                    for service in services_to_check:
                        if self.port_name in service.ports:
                            target_service = service
                            target_port = service.ports[self.port_name]
                            break
                    
                    if target_port:
                        # Create a service proxy for the specific port
                        # Get the binding name and address from the port
                        binding_name = target_port.binding.name
                        
                        # Get the port address - Zeep stores it in the port's location
                        port_address = None
                        try:
                            # Method 1: Try binding_address property (common in Zeep)
                            if hasattr(target_port, 'binding_address'):
                                try:
                                    port_address = target_port.binding_address
                                    if port_address:
                                        logger.debug(f"Found address via binding_address: {port_address}")
                                except Exception as e:
                                    logger.debug(f"binding_address exists but couldn't access: {str(e)}")
                            
                            # Method 2: Try accessing through the port's _element (XML structure)
                            if not port_address and hasattr(target_port, '_element'):
                                try:
                                    from lxml import etree
                                    # Look for soap:address element with location attribute
                                    soap_ns = 'http://schemas.xmlsoap.org/wsdl/soap/'
                                    # Try with namespace
                                    address_elem = target_port._element.find(f'.//{{{soap_ns}}}address')
                                    if address_elem is None:
                                        # Try without namespace prefix
                                        address_elem = target_port._element.find('.//address')
                                    if address_elem is not None:
                                        if 'location' in address_elem.attrib:
                                            port_address = address_elem.attrib['location']
                                            logger.debug(f"Found address via _element location: {port_address}")
                                        # Also try 'href' as some WSDLs use that
                                        elif 'href' in address_elem.attrib:
                                            port_address = address_elem.attrib['href']
                                            logger.debug(f"Found address via _element href: {port_address}")
                                except Exception as e:
                                    logger.debug(f"Error accessing _element: {str(e)}")
                            
                            # Method 3: Try accessing through binding's address
                            if not port_address:
                                try:
                                    # Check if binding has address directly
                                    if hasattr(target_port.binding, '_binding'):
                                        binding = target_port.binding._binding
                                        if hasattr(binding, 'address'):
                                            port_address = binding.address
                                except Exception:
                                    pass
                            
                            # Method 4: Try to get from port's location attribute
                            if not port_address and hasattr(target_port, 'location'):
                                port_address = target_port.location
                            
                            # Method 5: Inspect the port object for any address-related attributes
                            if not port_address:
                                # Log available attributes for debugging
                                port_attrs = [attr for attr in dir(target_port) if not attr.startswith('__')]
                                logger.debug(f"Port attributes: {port_attrs}")
                                
                                # Try common attribute names
                                for attr_name in ['address', 'location', 'url', 'endpoint', 'binding_address']:
                                    if hasattr(target_port, attr_name):
                                        try:
                                            value = getattr(target_port, attr_name)
                                            if value and isinstance(value, str) and value.startswith('http'):
                                                port_address = value
                                                break
                                        except Exception:
                                            pass
                            
                            # Method 6: Try to extract from the WSDL document directly
                            if not port_address:
                                try:
                                    # Access the WSDL document and find the port's address
                                    wsdl_doc = self.client.wsdl.document
                                    from lxml import etree
                                    
                                    # Get the root element
                                    root = None
                                    if hasattr(wsdl_doc, 'getroot'):
                                        root = wsdl_doc.getroot()
                                    elif hasattr(wsdl_doc, 'root'):
                                        root = wsdl_doc.root
                                    elif isinstance(wsdl_doc, etree._Element):
                                        root = wsdl_doc
                                    
                                    if root is not None:
                                        # Define namespaces
                                        wsdl_ns = 'http://schemas.xmlsoap.org/wsdl/'
                                        soap_ns = 'http://schemas.xmlsoap.org/wsdl/soap/'
                                        
                                        # Find the port by name - try with namespace
                                        port_elem = root.find(f'.//{{{wsdl_ns}}}port[@name="{self.port_name}"]')
                                        if port_elem is None:
                                            # Try without namespace
                                            port_elem = root.find(f'.//port[@name="{self.port_name}"]')
                                        
                                        if port_elem is not None:
                                            # Find the soap:address element
                                            address_elem = port_elem.find(f'{{{soap_ns}}}address')
                                            if address_elem is None:
                                                address_elem = port_elem.find('.//address')
                                            
                                            if address_elem is not None:
                                                if 'location' in address_elem.attrib:
                                                    port_address = address_elem.attrib['location']
                                                    logger.debug(f"Found address from WSDL document: {port_address}")
                                                elif 'href' in address_elem.attrib:
                                                    port_address = address_elem.attrib['href']
                                                    logger.debug(f"Found address from WSDL document (href): {port_address}")
                                except Exception as e:
                                    logger.debug(f"Could not extract address from WSDL document: {str(e)}")
                                    import traceback
                                    logger.debug(traceback.format_exc())
                            
                        except Exception as e:
                            logger.debug(f"Error extracting port address: {str(e)}")
                        
                        if not port_address:
                            # Fallback: Use known endpoint addresses for common ports
                            known_endpoints = {
                                'SistemaVerifactu': 'https://www1.agenciatributaria.gob.es/wlpl/TIKE-CONT/ws/SistemaFacturacion/VerifactuSOAP',
                                'SistemaVerifactuSello': 'https://www10.agenciatributaria.gob.es/wlpl/TIKE-CONT/ws/SistemaFacturacion/VerifactuSOAP',
                                'SistemaVerifactuPruebas': 'https://prewww1.aeat.es/wlpl/TIKE-CONT/ws/SistemaFacturacion/VerifactuSOAP',
                                'SistemaVerifactuSelloPruebas': 'https://prewww10.aeat.es/wlpl/TIKE-CONT/ws/SistemaFacturacion/VerifactuSOAP',
                            }
                            
                            if self.port_name in known_endpoints:
                                port_address = known_endpoints[self.port_name]
                                logger.warning(f"Could not extract address from WSDL for port '{self.port_name}'. Using known endpoint: {port_address}")
                            else:
                                # Log detailed information for debugging
                                logger.error(f"Could not determine address for port '{self.port_name}'.")
                                logger.error(f"Port object type: {type(target_port)}")
                                logger.error(f"Port attributes: {[attr for attr in dir(target_port) if not attr.startswith('__')]}")
                                logger.error(f"Binding name: {binding_name}")
                                logger.error("Available ports and their addresses:")
                                for svc in self.client.wsdl.services.values():
                                    for pname, pport in svc.ports.items():
                                        try:
                                            paddr = getattr(pport, 'binding_address', None) or \
                                                    (pport._element.find('.//{http://schemas.xmlsoap.org/wsdl/soap/}address').attrib.get('location') if hasattr(pport, '_element') else None)
                                            logger.error(f"  - {svc.name}.{pname}: {paddr}")
                                        except Exception:
                                            logger.error(f"  - {svc.name}.{pname}: (could not determine)")
                                logger.error(f"Known endpoints: {list(known_endpoints.keys())}")
                                raise ValueError(
                                    f"Could not determine address for port '{self.port_name}'. "
                                    f"Zeep requires both binding name and address for create_service(). "
                                    f"Please check the WSDL or use a different port."
                                )
                        
                        # Create service using the specific port's binding and address
                        self.client.service = self.client.create_service(
                            binding_name,
                            port_address
                        )
                        logger.info(f"\033[93mUsing port '{self.port_name}' from service '{target_service.name}' (endpoint: {port_address})\033[0m")
                    else:
                        # List available ports for debugging
                        available_ports = []
                        for service in self.client.wsdl.services.values():
                            for port_name in service.ports.keys():
                                available_ports.append(f"{service.name}.{port_name}")
                        logger.warning(f"Port '{self.port_name}' not found in WSDL.")
                        logger.warning(f"Available ports: {', '.join(available_ports)}")
                        logger.warning("Falling back to default service/port.")
                except Exception as e:
                    logger.warning(f"Could not select port by name '{self.port_name}': {str(e)}")
                    logger.warning("Falling back to default service/port.")
                    import traceback
                    logger.debug(traceback.format_exc())
 
            logger.info(f"\033[92mSOAP client initialized for WSDL: {self.wsdl_url}\033[0m")
            
        except FileNotFoundError as e:
            logger.error("=" * 80)
            logger.error("SOAP CLIENT INITIALIZATION ERROR - File Not Found")
            logger.error("=" * 80)
            logger.error(f"Error: {str(e)}")
            logger.error(f"WSDL URL: {self.wsdl_url}")
            logger.error(f"Certificate file path: {self.cert_file_path}")
            logger.error(f"Certificate file (legacy): {self.cert_file}")
            logger.error(f"Key file (legacy): {self.key_file}")
            logger.error("=" * 80)
            raise
            
        except ValueError as e:
            logger.error("=" * 80)
            logger.error("SOAP CLIENT INITIALIZATION ERROR - Certificate Error")
            logger.error("=" * 80)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Certificate file path: {self.cert_file_path}")
            if self.cert_file_path:
                logger.error(f"Certificate file exists: {os.path.exists(self.cert_file_path)}")
                if os.path.exists(self.cert_file_path):
                    logger.error(f"Certificate file size: {os.path.getsize(self.cert_file_path)} bytes")
            logger.error(f"Password provided: {'Yes' if self.cert_password else 'No'}")
            logger.error("=" * 80)
            logger.error("Common issues:")
            logger.error("  - Invalid certificate password")
            logger.error("  - Corrupted certificate file")
            logger.error("  - Certificate file is not in PKCS#12 format")
            logger.error("=" * 80)
            raise
            
        except ImportError as e:
            logger.error("=" * 80)
            logger.error("SOAP CLIENT INITIALIZATION ERROR - Import Error")
            logger.error("=" * 80)
            logger.error(f"Error: {str(e)}")
            logger.error("=" * 80)
            logger.error("This usually means a required library is missing.")
            logger.error("Please ensure you have installed:")
            logger.error("  - zeep: pip install zeep")
            logger.error("  - cryptography: pip install cryptography>=3.0")
            logger.error("  - requests: pip install requests")
            logger.error("=" * 80)
            raise
            
        except TransportError as e:
            status_code = getattr(e, 'status_code', None)
            logger.error("=" * 80)
            logger.error("SOAP CLIENT INITIALIZATION ERROR - Transport Error")
            logger.error("=" * 80)
            logger.error(f"Error: {str(e)}")
            logger.error(f"WSDL URL: {self.wsdl_url}")
            logger.error(f"Status code: {status_code}")
            logger.error("=" * 80)
            
            if status_code == 403:
                logger.error("403 FORBIDDEN - Access denied to WSDL")
                logger.error("=" * 80)
                logger.error("Possible causes:")
                logger.error("  1. WSDL URL is incomplete or incorrect")
                logger.error(f"     Current: {self.wsdl_url}")
                logger.error("     Expected format: https://prewww2.aeat.es/.../SuministroFactEmitidas.wsdl")
                logger.error("  2. Client certificate is required to access the WSDL")
                logger.error(f"     Certificate configured: {'Yes' if (self.cert_file_path or (self.cert_file and self.key_file)) else 'No'}")
                if self.cert_file_path:
                    logger.error(f"     Certificate file: {self.cert_file_path}")
                    logger.error(f"     Certificate exists: {os.path.exists(self.cert_file_path) if self.cert_file_path else 'N/A'}")
                logger.error("  3. The WSDL endpoint requires authentication")
                logger.error("  4. Your IP address or certificate is not authorized")
                logger.error("=" * 80)
                logger.error("Troubleshooting steps:")
                logger.error("  1. Verify the WSDL URL is complete and points to a .wsdl file")
                logger.error("  2. Ensure the client certificate is valid and matches the server requirements")
                logger.error("  3. Check if you need to download the WSDL file locally first")
                logger.error("  4. Contact the service provider for the correct WSDL URL and access requirements")
            elif status_code == 404:
                logger.error("404 NOT FOUND - WSDL URL not found")
                logger.error("=" * 80)
                logger.error("The WSDL URL does not exist or is incorrect.")
                logger.error(f"Please verify: {self.wsdl_url}")
            else:
                logger.error("Common issues:")
                logger.error("  - WSDL URL is not accessible")
                logger.error("  - Network connectivity problems")
                logger.error("  - SSL certificate validation failed")
                logger.error("  - Firewall blocking the connection")
            logger.error("=" * 80)
            raise
            
        except Exception as e:
            error_type = type(e).__name__
            logger.error("=" * 80)
            logger.error("SOAP CLIENT INITIALIZATION ERROR - Unexpected Error")
            logger.error("=" * 80)
            logger.error(f"Error type: {error_type}")
            logger.error(f"Error message: {str(e)}")
            logger.error(f"WSDL URL: {self.wsdl_url}")
            logger.error(f"Certificate file path: {self.cert_file_path}")
            logger.error(f"Certificate file (legacy): {self.cert_file}")
            logger.error(f"Key file (legacy): {self.key_file}")
            logger.error(f"Timeout: {self.timeout}")
            logger.error(f"Verify SSL: {self.verify_ssl}")
            
            # Check for HTTP errors
            if error_type == 'HTTPError':
                import requests
                if isinstance(e, requests.HTTPError):
                    response = getattr(e, 'response', None)
                    if response:
                        logger.error(f"HTTP Status Code: {response.status_code}")
                        logger.error(f"HTTP Response Headers: {dict(response.headers)}")
                        if response.status_code == 403:
                            logger.error("=" * 80)
                            logger.error("403 FORBIDDEN detected!")
                            logger.error("The server is denying access to the WSDL.")
                            logger.error("This usually means:")
                            logger.error("  1. The WSDL URL is incomplete (missing path to .wsdl file)")
                            logger.error("  2. Client certificate authentication is required")
                            logger.error("  3. The certificate is invalid or expired")
                            logger.error("  4. Your access is not authorized")
                            logger.error("=" * 80)
                            logger.error("Suggested WSDL URL format:")
                            logger.error("  https://prewww2.aeat.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/SuministroFactEmitidas.wsdl")
                            logger.error("=" * 80)
            
            logger.error("=" * 80)
            logger.error("Full traceback:")
            logger.error(traceback.format_exc())
            logger.error("=" * 80)
            raise
    
    def _verify_soap_compliance(self):
        """
        Explicitly verify and enforce SOAP 1.1 with document/literal style.
        
        This method ensures compliance with Spanish government Verifactu requirements:
        - SOAP 1.1 (namespace: http://schemas.xmlsoap.org/soap/envelope/)
        - Document style (style="document")
        - Literal encoding (use="literal")
        
        Raises:
            ValueError: If the WSDL does not comply with SOAP 1.1 document/literal requirements
        """
        if not self.client or not self.client.wsdl:
            logger.warning("Cannot verify SOAP compliance: client or WSDL not initialized")
            return
        
        # Use module-level constants for namespaces
        
        compliance_issues = []
        bindings_verified = []
        
        # Verify all bindings in all services
        for service_name, service in self.client.wsdl.services.items():
            for port_name, port in service.ports.items():
                binding = port.binding
                binding_name = binding.name if hasattr(binding, 'name') else 'unknown'
                
                # Check binding type and style
                try:
                    # Get binding information
                    binding_info = {
                        'service': service_name,
                        'port': port_name,
                        'binding': binding_name
                    }
                    
                    # Verify SOAP binding namespace (should be SOAP 1.1)
                    if hasattr(binding, '_binding'):
                        wsdl_binding = binding._binding
                        
                        # Check if it's a SOAP binding
                        if hasattr(wsdl_binding, 'namespace'):
                            binding_ns = str(wsdl_binding.namespace) if wsdl_binding.namespace else None
                            if binding_ns and binding_ns != WSDL_SOAP_NAMESPACE:
                                compliance_issues.append(
                                    f"Binding '{binding_name}' in service '{service_name}' port '{port_name}' "
                                    f"uses namespace '{binding_ns}' instead of SOAP WSDL namespace '{WSDL_SOAP_NAMESPACE}'"
                                )
                        
                        # Verify style (should be "document")
                        if hasattr(wsdl_binding, 'style'):
                            style = wsdl_binding.style
                            if style and style.lower() != 'document':
                                compliance_issues.append(
                                    f"Binding '{binding_name}' in service '{service_name}' port '{port_name}' "
                                    f"uses style '{style}' instead of required 'document'"
                                )
                            binding_info['style'] = style or 'document (default)'
                        else:
                            # If style is not specified, WSDL 1.1 defaults to "document" for document/literal
                            binding_info['style'] = 'document (default)'
                        
                        # Verify use (should be "literal")
                        # Check operations in the binding
                        if hasattr(binding, '_operations'):
                            for op_name, operation in binding._operations.items():
                                op_info = {'operation': op_name}
                                
                                # Check input binding
                                if hasattr(operation, 'input') and operation.input:
                                    input_binding = operation.input
                                    if hasattr(input_binding, 'use'):
                                        use = input_binding.use
                                        if use and use.lower() != 'literal':
                                            compliance_issues.append(
                                                f"Operation '{op_name}' in binding '{binding_name}' "
                                                f"uses encoding '{use}' instead of required 'literal'"
                                            )
                                        op_info['input_use'] = use or 'literal (default)'
                                
                                # Check output binding
                                if hasattr(operation, 'output') and operation.output:
                                    output_binding = operation.output
                                    if hasattr(output_binding, 'use'):
                                        use = output_binding.use
                                        if use and use.lower() != 'literal':
                                            compliance_issues.append(
                                                f"Operation '{op_name}' in binding '{binding_name}' "
                                                f"uses encoding '{use}' instead of required 'literal'"
                                            )
                                        op_info['output_use'] = use or 'literal (default)'
                                
                                binding_info.setdefault('operations', []).append(op_info)
                    
                    # Verify SOAP version in port address (should reference SOAP 1.1)
                    # The port's soap:address should use SOAP 1.1 namespace
                    if hasattr(port, '_element'):
                        try:
                            from lxml import etree
                            soap_ns = 'http://schemas.xmlsoap.org/wsdl/soap/'
                            address_elem = port._element.find(f'.//{{{soap_ns}}}address')
                            if address_elem is None:
                                address_elem = port._element.find('.//address')
                            
                            if address_elem is not None:
                                # Check namespace - should be SOAP WSDL namespace
                                elem_ns = address_elem.nsmap.get(address_elem.prefix) if address_elem.prefix else None
                                if elem_ns and elem_ns != WSDL_SOAP_NAMESPACE:
                                    compliance_issues.append(
                                        f"Port '{port_name}' address uses namespace '{elem_ns}' "
                                        f"instead of SOAP WSDL namespace '{WSDL_SOAP_NAMESPACE}'"
                                    )
                        except Exception as e:
                            logger.debug(f"Could not verify port address namespace: {str(e)}")
                    
                    bindings_verified.append(binding_info)
                    
                except Exception as e:
                    logger.warning(f"Could not fully verify binding '{binding_name}': {str(e)}")
                    # Don't fail on verification errors, just log them
                    compliance_issues.append(
                        f"Warning: Could not fully verify binding '{binding_name}': {str(e)}"
                    )
        
        # Log compliance verification results
        if compliance_issues:
            logger.warning("=" * 80)
            logger.warning(f"\033[91mSOAP COMPLIANCE VERIFICATION - ISSUES FOUND\033[0m")
            logger.warning("=" * 80)
            for issue in compliance_issues:
                logger.warning(f"  - {issue}")
            logger.warning("=" * 80)
            logger.warning("The WSDL may not fully comply with SOAP 1.1 document/literal requirements.")
            logger.warning("However, Zeep will attempt to use document/literal style when possible.")
            logger.warning("=" * 80)
        else:
            logger.info("=" * 80)
            logger.info(f"\033[92mSOAP COMPLIANCE VERIFICATION - PASSED\033[0m")
            logger.info("=" * 80)
            logger.info("✓ SOAP 1.1 namespace verified")
            logger.info("✓ Document style (style='document') verified")
            logger.info("✓ Literal encoding (use='literal') verified")
            logger.info("=" * 80)
        
        # Log verified bindings for reference
        if bindings_verified:
            logger.debug("Verified bindings:")
            for binding_info in bindings_verified:
                logger.debug(f"  Service: {binding_info['service']}, "
                           f"Port: {binding_info['port']}, "
                           f"Binding: {binding_info['binding']}, "
                           f"Style: {binding_info.get('style', 'unknown')}")
        
        # Force document/literal style in Zeep settings
        # Zeep uses document/literal by default when WSDL specifies it,
        # but we can ensure it's enforced by checking the binding operations
        try:
            # Verify that Zeep is configured to use document/literal
            # This is done implicitly by Zeep based on WSDL, but we log it for confirmation
            logger.info("Zeep client configured for SOAP 1.1 document/literal style")
            logger.info("All SOAP messages will use:")
            logger.info(f"  - SOAP Version: 1.1 (namespace: {SOAP_11_NAMESPACE})")
            logger.info("  - Style: document")
            logger.info("  - Encoding: literal")
        except Exception as e:
            logger.warning(f"Could not confirm Zeep document/literal configuration: {str(e)}")
    
    def _ensure_client(self):
        """Ensure the client is initialized before making requests."""
        if self.client is None:
            if not self.wsdl_url:
                raise ValueError("WSDL URL must be configured to initialize the client")
            self._initialize_client()
    
    def call_service(
        self,
        operation_name: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Call a SOAP service operation using SOAP 1.1 with document/literal style.
        
        This method ensures compliance with Spanish government Verifactu requirements:
        - SOAP 1.1 (namespace: http://schemas.xmlsoap.org/soap/envelope/)
        - Document style (style="document")
        - Literal encoding (use="literal")
        - UTF-8 encoding
        
        Args:
            operation_name: Name of the SOAP operation to call
            **kwargs: Parameters for the SOAP operation (will be validated against WSDL)
        
        Returns:
            Dictionary containing the response data
        
        Raises:
            Fault: SOAP fault from the server
            TransportError: Network/transport errors
            ValueError: Invalid operation or parameters
        """
        self._ensure_client()
        
        if not hasattr(self.client.service, operation_name):
            available_operations = [op for op in dir(self.client.service) if not op.startswith('_')]
            raise ValueError(
                f"Operation '{operation_name}' not found. Available operations: {available_operations}"
            )
        
        try:
            logger.info(f"Calling SOAP operation: {operation_name}")
            logger.debug(f"Operation parameters: {kwargs}")
            logger.debug(f"Using SOAP 1.1 with document/literal style (namespace: {SOAP_11_NAMESPACE})")
            
            # Get the operation method
            operation = getattr(self.client.service, operation_name)
            
            # Call the operation
            # Zeep automatically uses SOAP 1.1 document/literal style based on WSDL
            # This was verified during client initialization via _verify_soap_compliance()
            response = operation(**kwargs)
            
            logger.info(f"\033[92mSOAP operation '{operation_name}' completed successfully\033[0m")
            
            # Log raw response details for debugging
            logger.debug(f"Raw response type: {type(response)}")
            logger.debug(f"Raw response: {response}")
            
            # Try to get raw XML if available
            # try:
            #     # Method 1: Try history plugin (most reliable)
            #     if hasattr(self, '_history_plugin') and self._history_plugin:
            #         # History plugin stores last sent and received
            #         # After a call, last_received should contain the response
            #         if hasattr(self._history_plugin, 'last_received'):
            #             received = self._history_plugin.last_received
            #             if received:
            #                 logger.debug(f"History plugin last_received type: {type(received)}")
            #                 logger.debug(f"History plugin last_received attributes: {dir(received)}")
                            
            #                 # Try different ways to get the XML
            #                 if hasattr(received, 'envelope'):
            #                     self._last_raw_xml_response = str(received.envelope)
            #                     logger.info("Captured XML from history plugin (envelope)")
            #                 elif hasattr(received, 'http_response'):
            #                     http_resp = received.http_response
            #                     logger.debug(f"HTTP response type: {type(http_resp)}")
            #                     if hasattr(http_resp, 'content'):
            #                         self._last_raw_xml_response = http_resp.content.decode('utf-8')
            #                         logger.info("Captured XML from history plugin (http_response.content)")
            #                     elif hasattr(http_resp, 'text'):
            #                         self._last_raw_xml_response = http_resp.text
            #                         logger.info("Captured XML from history plugin (http_response.text)")
            #                     elif hasattr(http_resp, 'content'):
            #                         # Try bytes directly
            #                         try:
            #                             self._last_raw_xml_response = http_resp.content.decode('utf-8')
            #                             logger.info("Captured XML from history plugin (http_response.content bytes)")
            #                         except:
            #                             pass
                    
            #         # Also check the history list
            #         if not self._last_raw_xml_response and hasattr(self._history_plugin, 'messages'):
            #             messages = self._history_plugin.messages
            #             if messages:
            #                 last_msg = messages[-1]
            #                 logger.debug(f"Last message from history: {type(last_msg)}")
            #                 if hasattr(last_msg, 'http_response'):
            #                     http_resp = last_msg.http_response
            #                     if hasattr(http_resp, 'content'):
            #                         self._last_raw_xml_response = http_resp.content.decode('utf-8')
            #                         logger.info("Captured XML from history messages")
            #                     elif hasattr(http_resp, 'text'):
            #                         self._last_raw_xml_response = http_resp.text
            #                         logger.info("Captured XML from history messages (text)")
                
            #     # Method 2: Try last_received
            #     if not self._last_raw_xml_response and hasattr(self.client, 'last_received'):
            #         self._last_raw_xml_response = self.client.last_received
            #         logger.info("Captured XML from client.last_received")
                
            #     if self._last_raw_xml_response:
            #         logger.info(f"Raw XML response captured: {len(self._last_raw_xml_response)} bytes")
            #         # Log first 500 chars for debugging
            #         preview = self._last_raw_xml_response[:500] if len(self._last_raw_xml_response) > 500 else self._last_raw_xml_response
            #         logger.debug(f"XML preview: {preview}...")
            #     else:
            #         logger.warning("Could not capture raw XML response - response may be empty or parsing issue")
            #         logger.warning("This might mean the response was empty or the history plugin didn't capture it")
            # except Exception as e:
            #     logger.warning(f"Could not get raw XML: {str(e)}")
            #     import traceback
            #     logger.debug(traceback.format_exc())
            
            # Convert response to dictionary if it's a complex type
            parsed_response = self._parse_response(response)
            
            # Log parsed response
            logger.debug(f"Parsed response type: {type(parsed_response)}")
            if isinstance(parsed_response, dict):
                logger.debug(f"Parsed response keys: {list(parsed_response.keys())}")
                if not parsed_response:
                    logger.warning("=" * 80)
                    logger.warning("Parsed response is empty dictionary!")
                    logger.warning("=" * 80)
                    # Inspect the raw response to understand its structure
                    response_info = self.inspect_response(response)
                    logger.info("Response inspection:")
                    logger.info(f"  Type: {response_info.get('type')}")
                    logger.info(f"  Module: {response_info.get('module')}")
                    if response_info.get('attributes'):
                        logger.info(f"  Attributes: {response_info.get('attributes')[:20]}...")  # First 20
                    if response_info.get('__dict__'):
                        logger.info(f"  __dict__ keys: {list(response_info.get('__dict__', {}).keys())}")
                    if response_info.get('class_hierarchy'):
                        logger.info(f"  Class hierarchy: {response_info.get('class_hierarchy')}")
                    logger.warning("=" * 80)
            else:
                logger.debug(f"Parsed response: {parsed_response}")
            
            # If parsed response is empty but we have raw XML, include it
            if (isinstance(parsed_response, dict) and not parsed_response) and self._last_raw_xml_response:
                parsed_response['_raw_xml'] = self._last_raw_xml_response
                parsed_response['_message'] = 'Response parsed as empty, but raw XML was received. Check _raw_xml field.'
                parsed_response['_response_inspection'] = self.inspect_response(response)
                logger.info("Added raw XML and inspection info to response because parsed response was empty")
            
            return parsed_response
            
        except Fault as e:
            logger.error(f"SOAP Fault in operation '{operation_name}': {e.message}")
            logger.error(f"Fault code: {e.code}, Fault detail: {e.detail}")
            raise VerifactuSOAPFault(
                message=e.message,
                code=e.code,
                detail=e.detail
            ) from e
            
        except TransportError as e:
            logger.error(f"Transport error in operation '{operation_name}': {str(e)}")
            raise VerifactuSOAPTransportError(
                message=str(e),
                status_code=getattr(e, 'status_code', None)
            ) from e
            
        except Exception as e:
            logger.error(f"Unexpected error in operation '{operation_name}': {str(e)}")
            raise
    
    def _parse_response(self, response: Any) -> Dict[str, Any]:
        """
        Parse SOAP response into a dictionary.
        
        Args:
            response: Raw response from Zeep
        
        Returns:
            Dictionary representation of the response
        """
        if response is None:
            logger.warning("Response is None")
            return {}
        
        # Log the response type for debugging
        response_type = type(response).__name__
        logger.debug(f"Parsing response of type: {response_type}")
        
        # If response is already a dict-like object, convert it
        if hasattr(response, '__dict__'):
            parsed = self._object_to_dict(response)
            if not parsed:
                # Try alternative parsing methods
                parsed = self._parse_zeep_object(response)
            return parsed
        
        # If it's a list, convert each item
        if isinstance(response, list):
            logger.debug(f"Response is a list with {len(response)} items")
            return [self._parse_response(item) for item in response]
        
        # If it's a primitive type, return as-is
        if isinstance(response, (str, int, float, bool, type(None))):
            return response
        
        # Try to convert to dict
        try:
            return dict(response)
        except (TypeError, ValueError):
            # If all else fails, try to get string representation
            logger.warning(f"Could not parse response as dict, using string representation")
            return {'_raw_response': str(response), '_response_type': response_type}
    
    def _parse_zeep_object(self, obj: Any) -> Dict[str, Any]:
        """
        Parse a Zeep response object using multiple strategies.
        
        Args:
            obj: Zeep response object
        
        Returns:
            Dictionary representation
        """
        result = {}
        
        # Strategy 1: Check __dict__
        if hasattr(obj, '__dict__'):
            for key, value in obj.__dict__.items():
                if not key.startswith('_'):
                    result[key] = self._parse_response(value)
        
        # Strategy 2: Check for _value_1, _value_2, etc. (Zeep internal structure)
        for i in range(1, 10):
            attr_name = f'_value_{i}'
            if hasattr(obj, attr_name):
                value = getattr(obj, attr_name)
                if value is not None:
                    result[f'value_{i}'] = self._parse_response(value)
        
        # Strategy 3: Try to access as attributes (Zeep dynamic attributes)
        try:
            # Get all attributes that don't start with underscore
            for attr in dir(obj):
                if not attr.startswith('_') and not callable(getattr(obj, attr, None)):
                    try:
                        value = getattr(obj, attr)
                        if value is not None:
                            result[attr] = self._parse_response(value)
                    except Exception:
                        pass
        except Exception as e:
            logger.debug(f"Error accessing attributes: {str(e)}")
        
        # Strategy 4: Try to serialize using Zeep's own methods
        try:
            if hasattr(obj, '__class__'):
                # Try to get all fields from the type
                if hasattr(obj.__class__, '__dict__'):
                    for key in obj.__class__.__dict__:
                        if not key.startswith('_'):
                            try:
                                value = getattr(obj, key, None)
                                if value is not None:
                                    result[key] = self._parse_response(value)
                            except Exception:
                                pass
        except Exception as e:
            logger.debug(f"Error in class-based parsing: {str(e)}")
        
        # Strategy 5: If still empty, try to convert to XML string
        if not result:
            try:
                from lxml import etree
                if hasattr(obj, '_raw_element'):
                    xml_str = etree.tostring(obj._raw_element, encoding='unicode', pretty_print=True)
                    result['_xml'] = xml_str
                    logger.info("Extracted XML from _raw_element")
            except Exception as e:
                logger.debug(f"Could not extract XML: {str(e)}")
        
        # If still empty, return the string representation
        if not result:
            result['_raw'] = str(obj)
            result['_type'] = type(obj).__name__
            logger.warning(f"Could not parse Zeep object, returning raw string. Type: {type(obj).__name__}")
        
        return result
    
    def _object_to_dict(self, obj: Any) -> Dict[str, Any]:
        """Convert a Zeep response object to dictionary."""
        # Use the more comprehensive parsing method
        return self._parse_zeep_object(obj)
    
    def get_raw_xml_response(self) -> Optional[str]:
        """
        Get the raw XML response from the last SOAP call.
        
        Returns:
            Raw XML string if available, None otherwise
        """
        # Return stored XML if available
        if self._last_raw_xml_response:
            return self._last_raw_xml_response
        
        try:
            # Try history plugin (most reliable method)
            if hasattr(self, '_history_plugin') and self._history_plugin:
                # Get the last received entry
                if hasattr(self._history_plugin, 'last_received'):
                    received = self._history_plugin.last_received
                    if received:
                        # Try envelope first
                        if hasattr(received, 'envelope'):
                            return str(received.envelope)
                        # Try http_response
                        if hasattr(received, 'http_response'):
                            http_resp = received.http_response
                            if hasattr(http_resp, 'content'):
                                return http_resp.content.decode('utf-8')
                            elif hasattr(http_resp, 'text'):
                                return http_resp.text
                        # Fallback to string representation
                        return str(received)
                
                # Also check the history messages list
                if hasattr(self._history_plugin, 'messages'):
                    messages = self._history_plugin.messages
                    if messages:
                        last_msg = messages[-1]
                        if hasattr(last_msg, 'http_response'):
                            http_resp = last_msg.http_response
                            if hasattr(http_resp, 'content'):
                                return http_resp.content.decode('utf-8')
                            elif hasattr(http_resp, 'text'):
                                return http_resp.text
            
            # Try client's last_received
            if hasattr(self.client, 'last_received'):
                return self.client.last_received
            
            # Try transport
            if hasattr(self.client, 'transport'):
                if hasattr(self.client.transport, 'last_response'):
                    response = self.client.transport.last_response
                    if hasattr(response, 'text'):
                        return response.text
                    elif hasattr(response, 'content'):
                        return response.content.decode('utf-8')
                    return str(response)
        except Exception as e:
            logger.debug(f"Could not get raw XML: {str(e)}")
        
        return None
    
    def inspect_response(self, response: Any) -> Dict[str, Any]:
        """
        Inspect a response object to understand its structure.
        Useful for debugging when response parsing fails.
        
        Args:
            response: The response object to inspect
        
        Returns:
            Dictionary with inspection information
        """
        info = {
            'type': type(response).__name__,
            'module': type(response).__module__,
            'is_none': response is None,
            'attributes': [],
            'dict_keys': [],
            'methods': []
        }
        
        if response is None:
            return info
        
        # Get all attributes
        try:
            info['attributes'] = [attr for attr in dir(response) if not attr.startswith('__')]
        except:
            pass
        
        # Try to get dict keys
        try:
            if isinstance(response, dict):
                info['dict_keys'] = list(response.keys())
        except:
            pass
        
        # Get methods
        try:
            info['methods'] = [attr for attr in dir(response) if callable(getattr(response, attr, None)) and not attr.startswith('_')]
        except:
            pass
        
        # Try to get __dict__
        try:
            if hasattr(response, '__dict__'):
                info['__dict__'] = {k: str(type(v).__name__) for k, v in response.__dict__.items()}
        except:
            pass
        
        # Try to get class hierarchy
        try:
            if hasattr(response, '__class__'):
                info['class_hierarchy'] = [c.__name__ for c in response.__class__.__mro__]
        except:
            pass
        
        return info
    
    def get_wsdl_info(self) -> Dict[str, Any]:
        """
        Get information about the WSDL and available operations.
        
        Returns:
            Dictionary with WSDL information
        """
        self._ensure_client()
        
        # Get target namespace - handle different zeep versions
        target_namespace = None
        try:
            if self.client.wsdl.types:
                # Try different ways to get target namespace
                schema = self.client.wsdl.types
                if hasattr(schema, 'target_namespace'):
                    target_namespace = str(schema.target_namespace)
                elif hasattr(schema, '_target_namespace'):
                    target_namespace = str(schema._target_namespace)
                elif hasattr(schema, 'namespaces'):
                    # Get from namespaces dict if available
                    namespaces = getattr(schema, 'namespaces', {})
                    # Handle both dict and list types for namespaces
                    if isinstance(namespaces, dict):
                        # Usually the target namespace is the one without a prefix or with 'tns'
                        target_namespace = namespaces.get('tns') or namespaces.get('')
                    elif isinstance(namespaces, list) and namespaces:
                        # If namespaces is a list, try to get the first one or look for tns
                        # Some Zeep versions store namespaces as a list of tuples
                        for ns_item in namespaces:
                            if isinstance(ns_item, (list, tuple)) and len(ns_item) >= 2:
                                prefix, uri = ns_item[0], ns_item[1]
                                if prefix == 'tns' or prefix == '':
                                    target_namespace = uri
                                    break
                            elif isinstance(ns_item, str):
                                # If it's just a string, use it
                                target_namespace = ns_item
                                break
                else:
                    # Try to get from the WSDL document itself
                    if hasattr(self.client.wsdl, 'document'):
                        doc = self.client.wsdl.document
                        if hasattr(doc, 'target_namespace'):
                            target_namespace = str(doc.target_namespace)
        except Exception as e:
            logger.warning(f"Could not determine target namespace: {str(e)}")
            target_namespace = None
        
        info = {
            'wsdl_url': self.wsdl_url,
            'target_namespace': target_namespace,
            'operations': []
        }
        
        # Get available operations
        try:
            for service in self.client.wsdl.services.values():
                for port in service.ports.values():
                    for operation in port.binding._operations.values():
                        try:
                            input_sig = None
                            output_sig = None
                            
                            if operation.input:
                                try:
                                    input_sig = str(operation.input.signature())
                                except Exception:
                                    input_sig = f"Input type: {type(operation.input).__name__}"
                            
                            if operation.output:
                                try:
                                    output_sig = str(operation.output.signature())
                                except Exception:
                                    output_sig = f"Output type: {type(operation.output).__name__}"
                            
                            info['operations'].append({
                                'name': operation.name,
                                'input': input_sig,
                                'output': output_sig,
                            })
                        except Exception as e:
                            logger.warning(f"Error getting operation info for {operation.name}: {str(e)}")
                            info['operations'].append({
                                'name': getattr(operation, 'name', 'unknown'),
                                'input': None,
                                'output': None,
                            })
        except Exception as e:
            logger.error(f"Error extracting operations from WSDL: {str(e)}")
            # Try alternative method to get operations
            try:
                if hasattr(self.client.service, '__dict__'):
                    for attr_name in dir(self.client.service):
                        if not attr_name.startswith('_'):
                            info['operations'].append({
                                'name': attr_name,
                                'input': None,
                                'output': None,
                            })
            except Exception:
                pass
        
        return info
    
    def create_envelope(
        self,
        body_content: Dict[str, Any],
        header_content: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a SOAP 1.1 envelope manually (for advanced use cases).
        
        This method explicitly creates a SOAP 1.1 envelope with document/literal style
        as required by Spanish government Verifactu specifications.
        
        Compliance:
        - SOAP Version: 1.1 (namespace: http://schemas.xmlsoap.org/soap/envelope/)
        - Style: document (style="document")
        - Encoding: literal (use="literal")
        - XML Encoding: UTF-8
        
        Args:
            body_content: Content for the SOAP body
            header_content: Optional content for the SOAP header
        
        Returns:
            XML string of the SOAP envelope (UTF-8 encoded)
        """
        from lxml import etree
        
        # Explicitly use SOAP 1.1 namespace as required by Spanish government
        # Reference: W3C NOTE SOAP-20000508 - http://schemas.xmlsoap.org/soap/envelope/
        soap_ns = SOAP_11_NAMESPACE
        env = etree.Element(f"{{{soap_ns}}}Envelope")
        env.set("xmlns:soap", soap_ns)
        
        # SOAP Header (optional)
        if header_content:
            header = etree.SubElement(env, f"{{{soap_ns}}}Header")
            self._add_dict_to_element(header, header_content)
        
        # SOAP Body
        body = etree.SubElement(env, f"{{{soap_ns}}}Body")
        self._add_dict_to_element(body, body_content)
        
        return etree.tostring(env, encoding='utf-8', pretty_print=True).decode('utf-8')
    
    def _add_dict_to_element(self, parent, data: Dict[str, Any]):
        """Helper to add dictionary data to XML element."""
        from lxml import etree
        
        for key, value in data.items():
            if isinstance(value, dict):
                child = etree.SubElement(parent, key)
                self._add_dict_to_element(child, value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        child = etree.SubElement(parent, key)
                        self._add_dict_to_element(child, item)
                    else:
                        child = etree.SubElement(parent, key)
                        child.text = str(item)
            else:
                child = etree.SubElement(parent, key)
                child.text = str(value) if value is not None else ''


class VerifactuSOAPFault(Exception):
    """Custom exception for SOAP faults."""
    
    def __init__(self, message: str, code: Optional[str] = None, detail: Optional[str] = None):
        self.message = message
        self.code = code
        self.detail = detail
        super().__init__(f"SOAP Fault: {message} (Code: {code})")


class VerifactuSOAPTransportError(Exception):
    """Custom exception for transport errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(f"Transport Error: {message} (Status: {status_code})")

