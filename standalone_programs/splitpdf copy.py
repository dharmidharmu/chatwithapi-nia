import os
from PyPDF2 import PdfReader, PdfWriter

def split_pdf_folder(input_folder, max_size_mb=5):
    # Convert max size to bytes
    max_size_bytes = max_size_mb * 1024 * 1024
    
    # Get all PDF files in the input folder
    pdf_files = [file for file in os.listdir(input_folder) if file.endswith('.pdf')]
    
    for pdf_file in pdf_files:
        input_pdf_path = os.path.join(input_folder, pdf_file)
        
        # Read the PDF file
        reader = PdfReader(input_pdf_path)
        total_pages = len(reader.pages)
        
        output_pdf_index = 1
        output_pdf = PdfWriter()
        output_pdf_size = 0

        for i in range(total_pages):
            output_pdf.add_page(reader.pages[i])
            
            # Write to a temporary file to check size
            temp_output_path = f'temp_output_{output_pdf_index}.pdf'
            with open(temp_output_path, 'wb') as temp_file:
                output_pdf.write(temp_file)
            
            # Get the size of the temporary file
            output_pdf_size = os.path.getsize(temp_output_path)
            
            if output_pdf_size >= max_size_bytes:
                # Finalize the current part
                final_output_path = f'{pdf_file}_output_part_{output_pdf_index}.pdf'
                os.rename(temp_output_path, final_output_path)
                print(f'Created: {final_output_path}')
                
                # Start a new PDF writer for the next part
                output_pdf = PdfWriter()
                output_pdf_index += 1
                output_pdf.add_page(reader.pages[i])  # Add the current page to new part

        # Write any remaining pages to a final PDF
        if len(output_pdf.pages) > 0:
            final_output_path = f'{pdf_file}_output_part_{output_pdf_index}.pdf'
            with open(final_output_path, 'wb') as final_file:
                output_pdf.write(final_file)
            print(f'Created: {final_output_path}')

        # Clean up temporary files
        if os.path.exists(temp_output_path):
            os.remove(temp_output_path)

# Example usage
input_folder = "C:/Users/rac7cob/Desktop/Azure Open AI Documentation/New folder"  # Replace with your input folder path
print("Started")
split_pdf_folder(input_folder)
print("Done")
