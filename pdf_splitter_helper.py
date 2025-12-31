import os
from pypdf import PdfReader, PdfWriter
from typing import List, Tuple, BinaryIO, Optional
import io

class PdfSplitterHelper:
    """
    Helper class for intelligently splitting PDF files based on size thresholds.
    """
    MAX_TOTAL_SIZE_MB = 30
    MEDIUM_FILE_THRESHOLD_MB = 10 # For splitting into 2 parts
    LARGE_FILE_THRESHOLD_MB = 20  # For splitting into 3 parts

    def __init__(self, temp_dir: str = "."):
        self.temp_dir = temp_dir
        os.makedirs(self.temp_dir, exist_ok=True)

    def _get_pdf_page_ranges(self, reader: PdfReader, num_fragments: int) -> List[Tuple[int, int]]:
        """
        Calculates page ranges for splitting a PDF into a given number of fragments.
        """
        total_pages = len(reader.pages)
        if num_fragments <= 0 or total_pages == 0:
            return []

        pages_per_fragment = total_pages // num_fragments
        ranges = []
        for i in range(num_fragments):
            start_page = i * pages_per_fragment
            end_page = (i + 1) * pages_per_fragment
            if i == num_fragments - 1: # Last fragment gets remaining pages
                end_page = total_pages
            ranges.append((start_page, end_page))
        return ranges

    def split_pdf(self, file_path: str) -> List[Tuple[bytes, str]]:
        """
        Splits a PDF file into multiple byte fragments based on size thresholds.

        Args:
            file_path (str): The path to the input PDF file.

        Returns:
            List[Tuple[bytes, str]]: A list of tuples, where each tuple contains
                                    (bytes of PDF fragment, temporary filename of fragment).

        Raises:
            ValueError: If the file exceeds MAX_TOTAL_SIZE_MB or splitting fails.
        """
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        print(f"  PDF Splitter: Analyzing file '{file_path}' (Size: {file_size_mb:.2f} MB)")

        if file_size_mb > self.MAX_TOTAL_SIZE_MB:
            raise ValueError(f"File '{file_path}' ({(file_size_mb):.2f} MB) exceeds maximum allowed size of {self.MAX_TOTAL_SIZE_MB} MB.")

        num_fragments = 1
        if file_size_mb >= self.LARGE_FILE_THRESHOLD_MB:
            num_fragments = 3
        elif file_size_mb >= self.MEDIUM_FILE_THRESHOLD_MB:
            num_fragments = 2

        reader = PdfReader(file_path)
        page_ranges = self._get_pdf_page_ranges(reader, num_fragments)

        output_fragments: List[Tuple[bytes, str]] = []
        for i, (start_page, end_page) in enumerate(page_ranges):
            writer = PdfWriter()
            for page_num in range(start_page, end_page):
                if page_num < len(reader.pages): # Ensure page exists
                    writer.add_page(reader.pages[page_num])
            
            output_buffer = io.BytesIO()
            writer.write(output_buffer)
            output_buffer.seek(0)
            
            fragment_filename = f"fragment_{i+1}_of_{num_fragments}.pdf"
            output_fragments.append((output_buffer.getvalue(), fragment_filename))
            print(f"  PDF Splitter: Created fragment {i+1} (Pages: {start_page+1}-{end_page})")

        return output_fragments

if __name__ == "__main__":
    # Example Usage (for testing the splitter logic)
    # This part will only run if you execute pdf_splitter_helper.py directly
    print("--- PDF Splitter Helper Test ---")
    
    # Create a dummy PDF for testing
    from pypdf import PdfWriter
    writer = PdfWriter()
    for _ in range(50): # 50 empty pages
        writer.add_blank_page(width=72, height=72)
    with open("dummy_large.pdf", "wb") as f:
        writer.write(f)
    print("Created 'dummy_large.pdf' (50 pages)")

    splitter = PdfSplitterHelper()
    
    try:
        # Test case 1: Small file (will not split)
        # Create a small dummy PDF
        writer_small = PdfWriter()
        for _ in range(5): writer_small.add_blank_page(width=72, height=72)
        with open("dummy_small.pdf", "wb") as f:
            writer_small.write(f)
        print("\nTesting 'dummy_small.pdf' (<10MB)...")
        fragments_small = splitter.split_pdf("dummy_small.pdf")
        print(f"  Fragments: {len(fragments_small)}")
        os.remove("dummy_small.pdf")

        # Test case 2: Medium file (will split into 2)
        # Assuming dummy_large.pdf is around 10-20MB for this test.
        # This requires adjusting the dummy PDF size to fit thresholds realistically.
        # For a more robust test, create files of specific sizes.
        print("\nTesting 'dummy_large.pdf' (assuming >10MB & <20MB for 2 fragments)...")
        # To simulate, let's assume dummy_large.pdf is 15MB.
        # This is a simplification; actual file size depends on content.
        # For real testing, you'd need PDFs of specific sizes.
        fragments_medium = splitter.split_pdf("dummy_large.pdf")
        print(f"  Fragments: {len(fragments_medium)}")
        
        # Test case 3: Large file (will split into 3)
        # To simulate, let's say dummy_large.pdf is actually 25MB.
        # This requires creating a larger dummy file for a realistic test.
        # For simplicity, we'll just run with the existing dummy_large.pdf.
        # In a real scenario, you'd need to create a PDF >20MB and <=30MB.
        print("\nTesting 'dummy_large.pdf' (assuming >20MB & <=30MB for 3 fragments)...")
        fragments_large = splitter.split_pdf("dummy_large.pdf")
        print(f"  Fragments: {len(fragments_large)}")
        
        # Clean up the test dummy PDF
        os.remove("dummy_large.pdf")

    except ValueError as e:
        print(f"\nError during testing: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred during testing: {e}")

    print("--- Test End ---")
