# Verifactu Module

Module for communicating with the Spanish government's Verifactu (Facturación Electrónica) service via SOAP.

## SOAP Implementation

This module implements SOAP 1.1 following Spanish government specifications:

- **Style**: Document (`style="document"`)
- **Encoding**: Literal (`use="literal"`)
- **Messages**: Fully described by XML schemas

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

The `zeep` library (version 4.2.1) is required for SOAP communication.

## Configuration

Add the following environment variables to your `.env` file:

```env
# WSDL URL for the Verifactu SOAP service
VERIFACTU_WSDL_URL=https://www.agenciatributaria.gob.es/.../SuministroFactEmitidas.wsdl

# PKCS#12 certificate file (.pfx or .p12) - RECOMMENDED
# Note: .pfx and .p12 are the same format, just different extensions
VERIFACTU_CERT_FILE_PATH=my-cert.pfx

# Password for the PKCS#12 certificate file
VERIFACTU_CERT_KEY=your_certificate_password

# Optional: SOAP request timeout (default: 30 seconds)
VERIFACTU_SOAP_TIMEOUT=30

# Optional: Verify SSL certificates (default: True)
VERIFACTU_VERIFY_SSL=True

# MANDATORY: NIF of the emitter
VERIFACTU_NIF=1234567890

# Optional: Select port by name (recommended for switching between production and testing)
# For prewww/testing environment, use:
VERIFACTU_PORT_NAME=SistemaVerifactuPruebas
# For production, omit this variable or use:
# VERIFACTU_PORT_NAME=SistemaVerifactu
```

### Using Pre-Production (Testing) Environment

To use the prewww (pre-production/testing) environment instead of production, you have two options:

#### Option 1: Select Port by Name (Recommended)

This is the preferred method as it uses the port definitions from the WSDL file directly.

1. **Set the port name** in your `.env` file:
```env
VERIFACTU_PORT_NAME=SistemaVerifactuPruebas
```

2. **Or specify it programmatically** when creating the client:
```python
from verifactu.utils.soap_client_service import VerifactuSOAPClient

# Use prewww/testing environment by selecting the port
client = VerifactuSOAPClient(
    port_name='SistemaVerifactuPruebas'
)

# You can also specify the service name if needed
client = VerifactuSOAPClient(
    service_name='sfVerifactu',
    port_name='SistemaVerifactuPruebas'
)
```

#### Option 2: Override Endpoint URL (Fallback)

If you prefer to override the endpoint URL directly:

1. **Set the service endpoint override** in your `.env` file:
```env
VERIFACTU_SERVICE_ENDPOINT=https://prewww1.aeat.es/wlpl/TIKE-CONT/ws/SistemaFacturacion/VerifactuSOAP
```

2. **Or specify it programmatically** when creating the client:
```python
from verifactu.utils.soap_client_service import VerifactuSOAPClient

# Use prewww/testing environment
client = VerifactuSOAPClient(
    service_endpoint='https://prewww1.aeat.es/wlpl/TIKE-CONT/ws/SistemaFacturacion/VerifactuSOAP'
)
```

**Available ports from the WSDL:**
- **Production (Verifactu)**: `SistemaVerifactu` → `https://www1.agenciatributaria.gob.es/wlpl/TIKE-CONT/ws/SistemaFacturacion/VerifactuSOAP`
- **Production (Verifactu with seal certificate)**: `SistemaVerifactuSello` → `https://www10.agenciatributaria.gob.es/wlpl/TIKE-CONT/ws/SistemaFacturacion/VerifactuSOAP`
- **Testing (Verifactu)**: `SistemaVerifactuPruebas` → `https://prewww1.aeat.es/wlpl/TIKE-CONT/ws/SistemaFacturacion/VerifactuSOAP`
- **Testing (Verifactu with seal certificate)**: `SistemaVerifactuSelloPruebas` → `https://prewww10.aeat.es/wlpl/TIKE-CONT/ws/SistemaFacturacion/VerifactuSOAP`

**Note**: The WSDL URL can remain the same for both environments. Using `port_name` is preferred as it uses the exact port definition from the WSDL, ensuring compatibility.

### Alternative: Separate PEM Files (Legacy)

If you prefer to use separate PEM certificate and key files:

```env
# Client certificate for authentication (PEM format)
VERIFACTU_CERT_FILE=/path/to/client_certificate.pem

# Client private key (PEM format)
VERIFACTU_KEY_FILE=/path/to/client_private_key.pem
```

**Note**: PKCS#12 format (`.pfx` or `.p12` - both are identical) is recommended as it's the standard format provided by the Spanish government. The code supports both extensions.

## Usage

### Basic Example

```python
from verifactu.utils.soap_client_service import VerifactuSOAPClient

# Initialize the client (uses configuration from environment)
client = VerifactuSOAPClient()

# Call a SOAP operation
response = client.call_service(
    operation_name='SubmitInvoice',
    invoice={
        'invoice_number': 'INV-001',
        'invoice_date': '2024-01-15',
        'amount': 1000.00
    }
)

print(response)
```

### Advanced Example with Custom Configuration

```python
from verifactu.utils.soap_client_service import VerifactuSOAPClient

# Initialize with custom configuration
client = VerifactuSOAPClient(
    wsdl_url='https://example.com/service.wsdl',
    timeout=60,
    verify_ssl=True,
    cert_file='/path/to/cert.pem',
    key_file='/path/to/key.pem'
)

# Get information about available operations
wsdl_info = client.get_wsdl_info()
print(f"Available operations: {[op['name'] for op in wsdl_info['operations']]}")

# Call an operation
response = client.call_service(
    operation_name='GetInvoiceStatus',
    invoice_id='INV-001'
)
```

### Error Handling

```python
from verifactu.utils.soap_client_service import (
    VerifactuSOAPClient,
    VerifactuSOAPFault,
    VerifactuSOAPTransportError
)

client = VerifactuSOAPClient()

try:
    response = client.call_service(
        operation_name='SubmitInvoice',
        invoice_data={...}
    )
except VerifactuSOAPFault as e:
    # Handle SOAP faults (validation errors, business logic errors)
    print(f"SOAP Fault: {e.message} (Code: {e.code})")
    print(f"Details: {e.detail}")
except VerifactuSOAPTransportError as e:
    # Handle transport errors (network issues, SSL problems)
    print(f"Transport Error: {e.message}")
    print(f"Status Code: {e.status_code}")
except Exception as e:
    # Handle other errors
    print(f"Unexpected error: {str(e)}")
```

### Creating Custom SOAP Envelopes

For advanced use cases where you need full control over the SOAP message:

```python
from verifactu.utils.soap_client_service import VerifactuSOAPClient

client = VerifactuSOAPClient()

# Create SOAP body content
body_content = {
    'SubmitInvoiceRequest': {
        'InvoiceNumber': 'INV-001',
        'InvoiceDate': '2024-01-15',
        'Amount': 1000.00,
        'Currency': 'EUR'
    }
}

# Optional: Create SOAP header
header_content = {
    'Authentication': {
        'Username': 'your_username',
        'Password': 'your_password'
    }
}

# Generate SOAP envelope
envelope_xml = client.create_envelope(
    body_content=body_content,
    header_content=header_content
)

print(envelope_xml)
```

## SOAP Message Structure

The client automatically generates SOAP 1.1 messages with the following structure:

```xml
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Header>
        <!-- Optional header content -->
    </soap:Header>
    <soap:Body>
        <!-- Operation-specific content based on WSDL schema -->
    </soap:Body>
</soap:Envelope>
```

## Features

- ✅ SOAP 1.1 compliant
- ✅ Document/literal style (as required by Spanish government)
- ✅ Automatic WSDL parsing
- ✅ Type validation based on XML schemas
- ✅ SSL/TLS client certificate authentication
- ✅ Comprehensive error handling
- ✅ Request/response logging
- ✅ Support for complex data types

## Testing

### Quick Test with Management Command

The easiest way to test the SOAP message is using the Django management command:

```bash
# Send the example SOAP message (requires WSDL configuration)
python manage.py test_verifactu_soap

# Just generate the XML envelope without sending
python manage.py test_verifactu_soap --xml-only
```

### Test Script

You can also use the test script directly:

```python
# In Django shell
python manage.py shell

>>> from verifactu.utils.test_soap_message import test_send_example_invoice
>>> test_send_example_invoice()
```

### Unit Tests

Run the Django test suite:

```bash
python manage.py test verifactu.tests.test_soap_invoice
```

### Example Invoice Message

The test includes the example "alta inicial" (initial registration) message from the Verifactu documentation:

- **Emisor**: NIF AAAA, Nombre XXXXX
- **Factura**: Serie 12345, Fecha 13-09-2024
- **Destinatario**: NIF BBBB, Nombre YYYY
- **Importe Total**: 131.4 EUR
- **Desglose**: Two tax lines (4% and 21% IVA)

See `verifactu/utils/test_soap_message.py` for the complete example structure.

## Notes

- The client automatically uses document/literal style based on the WSDL definition
- All messages are validated against the XML schemas defined in the WSDL
- Client certificates are required for authentication with the Spanish government service
- The WSDL URL and certificate paths should be kept secure and not committed to version control

