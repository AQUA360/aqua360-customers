import io
import fitz  # PyMuPDF
from PIL import Image
import numpy as np
from django.core.files.storage import default_storage
from tempfile import NamedTemporaryFile

def add_watermark_to_pdf(pdf_buffer, watermark_path, gradient=False, opacity=0.3):
    """Apply a watermark image to every page of a PDF stored in memory."""
    
    if gradient:
        watermark_bytes = reduce_opacity_with_gradient(watermark_path)
    else:
        watermark_bytes = reduce_opacity(watermark_path, opacity)

    # Convert watermark to PyMuPDF Pixmap
    watermark = fitz.Pixmap(watermark_bytes)

    # Load the PDF from memory
    pdf_document = fitz.open(stream=pdf_buffer.getvalue(), filetype="pdf")

    for page in pdf_document:
        rect = page.rect  # Get the page dimensions

        # Define watermark size and position (adjust as needed)
        img_width = rect.width  # Scale watermark to 50% of page width
        img_height = (watermark.height / watermark.width) * img_width  # Keep aspect ratio
        img_x = (rect.width - img_width) / 2  # Center horizontally
        img_y = (rect.height - img_height) / 2 if not gradient else (rect.height - img_height) / 3

        # Define where to place the watermark
        img_rect = fitz.Rect(img_x, img_y, img_x + img_width, img_y + img_height)

        # Overlay the image
        page.insert_image(img_rect, pixmap=watermark, overlay=(not gradient))

    # Save the modified PDF to memory
    output_buffer = io.BytesIO()
    pdf_document.save(output_buffer)
    pdf_document.close()
    
    return output_buffer

def reduce_opacity(image_path, opacity=0.3):
    """Reduce opacity of a PNG image and return it as a BytesIO object."""
    img = Image.open(image_path).convert("RGBA")  # Ensure it's RGBA (with alpha)
    
    # Resize if image is too large (max 2000px on longest side to reduce file size)
    max_dimension = 2000
    if max(img.size) > max_dimension:
        ratio = max_dimension / max(img.size)
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
    
    alpha = img.split()[3]  # Extract the alpha channel
    alpha = alpha.point(lambda p: int(p * opacity))  # Reduce opacity
    img.putalpha(alpha)  # Apply new transparency

    # Save modified image to memory with compression
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG", optimize=True, compress_level=9)
    img_bytes.seek(0)
    
    return img_bytes

def reduce_opacity_with_gradient(image_path, base_opacity=1):
    img = Image.open(image_path).convert("RGBA")
    
    # Resize if image is too large (max 2000px on longest side to reduce file size)
    max_dimension = 2000
    if max(img.size) > max_dimension:
        ratio = max_dimension / max(img.size)
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
    
    img_array = np.array(img)
    
    height, width = img_array.shape[:2]
    
    gradient = np.linspace(1.0, 0.0, height)[:, np.newaxis]
    
    img_array[:, :, 3] = (img_array[:, :, 3] * gradient * base_opacity).astype(np.uint8)
    
    img_gradient = Image.fromarray(img_array, 'RGBA')
    
    img_bytes = io.BytesIO()
    img_gradient.save(img_bytes, format="PNG", optimize=True, compress_level=9)
    img_bytes.seek(0)
    
    return img_bytes

def merge_pdfs(*invoices):
    merged_pdf = fitz.open()
    
    for invoice in invoices:
        if invoice.invoice_file_template:
            with default_storage.open(invoice.invoice_file_template.name, 'rb') as f:
                pdf = fitz.open("pdf", f.read())
                merged_pdf.insert_pdf(pdf)
    
    temp_file = NamedTemporaryFile(suffix=".pdf", delete=False)
    merged_pdf.save(temp_file.name)
    merged_pdf.close()
    return temp_file