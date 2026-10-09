import base64
import json
import qrcode
import io
import hashlib
# ----------------------------
# Generate QR (base64 PNG)
# ----------------------------
def generate_qr_base64(payload_text: str) -> str:
    qr = qrcode.QRCode(box_size=4, border=2)
    qr.add_data(payload_text)
    qr.make(fit=True)
    img = qr.make_image()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b = buf.getvalue()
    return base64.b64encode(b).decode('ascii')