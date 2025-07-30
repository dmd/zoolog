import fitz  # PyMuPDF
from PIL import Image
import io

def mirror_pdf(input_pdf, output_pdf):
    # Open the input PDF
    doc = fitz.open(input_pdf)
    
    # Create a new PDF to save the mirrored pages
    new_doc = fitz.open()

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        pix = page.get_pixmap()

        # Convert pixmap to PIL Image
        img = Image.open(io.BytesIO(pix.tobytes("png")))

        # Mirror the image
        mirrored_img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)

        # Convert the mirrored image back to pixmap
        mirrored_img_byte_arr = io.BytesIO()
        mirrored_img.save(mirrored_img_byte_arr, format='PNG')
        mirrored_img_byte_arr.seek(0)
        mirrored_pix = fitz.Pixmap(mirrored_img_byte_arr)

        # Create a new page in the new PDF with the same dimensions
        new_page = new_doc.new_page(width=page.rect.width, height=page.rect.height)

        # Draw the mirrored pixmap on the new page
        new_page.insert_image(new_page.rect, pixmap=mirrored_pix)

    # Save the new PDF
    new_doc.save(output_pdf)

# Example usage
input_pdf = "input.pdf"
output_pdf = "mirrored_output.pdf"
mirror_pdf(input_pdf, output_pdf)
