import os
import re
import csv
import io
import traceback
from google.genai import types # Import types directly for types.Part
from gemini_orchestrator import GeminiOrchestrator
from google_drive_helper import GoogleDriveHelper
from google_sheets_helper import GoogleSheetsHelper
from typing import List, Union # Added import for List

class _KnowledgeBaseLoader:
    """
    Internal class responsible for loading and preparing the knowledge base
    (prompts and checklist) for the Gemini model.
    """

    def __init__(self, drive_helper: GoogleDriveHelper, gemini_orchestrator: GeminiOrchestrator, config: dict):
        """
        Initializes the knowledge base loader.

        Args:
            drive_helper (GoogleDriveHelper): Helper to interact with Google Drive.
            gemini_orchestrator (GeminiOrchestrator): Helper to interact with Gemini.
            config (dict): Configuration dictionary. Expected keys:
                - 'prompt_url' (str): URL of the prompts file.
                - 'checklist_url' (str): URL of the checklist spreadsheet.
                - 'sow_url' (str): URL of the Statement of Work (SOW) PDF file. # Assuming SOW will be handled here
        """
        self.drive = drive_helper
        self.gemini = gemini_orchestrator
        self.config = config
        self.uploaded_files_to_track = [] # For Developer API mode, to track Gemini File resources

    def _load_and_parse_prompts(self) -> tuple[str, list]:
        """Downloads and parses the prompts file from Google Drive."""
        print("  - 📥 Downloading and parsing prompts...")
        prompt_file_id = self.drive.get_id_from_url(self.config['prompt_url'])
        prompt_content_bytes = self.drive.download_file_content(prompt_file_id)
        prompt_content = prompt_content_bytes.decode('utf-8')

        parts = re.split(r'### Prompt \d+:', prompt_content)
        system_block = parts[1].strip()
        system_instr_match = re.search(r'System Instructions\s*\n(.+)', system_block, re.DOTALL)
        system_instructions = system_instr_match.group(1).strip() if system_instr_match else ""

        prompt_sequence = []
        for i, part in enumerate(parts[2:], start=1):
            clean_text = re.sub(r'^.*\n', '', part, 1).strip()
            # This regex will be updated to handle the new attachment logic
            clean_text = re.sub(r'\*\*\[Attached File:.*\]\*\*\s*\n?', '', clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r'^\*\*Text:\*\*\s*\n?', '', clean_text, flags=re.IGNORECASE).strip()
            prompt_sequence.append({'id': i, 'text': clean_text})
        print("  - ✅ Prompts parsed.")
        return system_instructions, prompt_sequence

    def _prepare_checklist_for_gemini(self) -> List[types.Part]: # Return type changed to List[types.Part]
        """
        Downloads the checklist, processes it for Gemini (upload or inline),
        and returns a list of types.Part objects.
        """
        print("  - ⚙️ Preparing checklist for Gemini...")
        
        # Added debug to check client mode just before upload preparation
        print(f"  DEBUG: GeminiOrchestrator client.vertexai state: {self.gemini.is_vertex_ai_mode()}")

        checklist_file_id = self.drive.get_id_from_url(self.config['checklist_url'])
        checklist_bytes = self.drive.export_file(checklist_file_id, mime_type='text/csv')

        checklist_filename = "checklist.csv"
        try:
            with open(checklist_filename, 'wb') as f:
                f.write(checklist_bytes)
            print(f"    - Checklist downloaded as '{checklist_filename}'.")
            
            # Use the orchestrator's new method for processing the file
            # This will return List[types.Part], encapsulating the file or its fragments
            gemini_checklist_parts = self.gemini.process_file_for_gemini(
                file_path=checklist_filename,
                mime_type='text/csv'
            )
            
            # If in Developer API mode, the uploaded files need to be tracked for cleanup
            if not self.gemini.is_vertex_ai_mode():
                # Assuming process_file_for_gemini returns [types.File] for Developer API
                # and we need to extract their names.
                for part in gemini_checklist_parts:
                    if isinstance(part, types.File): # Check if it's a types.File object
                        self.uploaded_files_to_track.append(part.name)
            
            return gemini_checklist_parts
        except Exception as e:
            print(f"  ❌ ERROR in _prepare_checklist_for_gemini: {e}")
            traceback.print_exc() # Print full traceback
            raise
        finally:
            if os.path.exists(checklist_filename):
                os.remove(checklist_filename)
                print(f"    - Temporary local file '{checklist_filename}' deleted.")

    def _prepare_sow_for_gemini(self) -> List[types.Part]: # New method for SOW
        """
        Downloads the SOW PDF, processes it for Gemini (splitting/inline),
        and returns a list of types.Part objects.
        """
        print("  - 📄 Preparing Statement of Work (SOW) PDF for Gemini...")
        sow_file_id = self.drive.get_id_from_url(self.config['sow_url'])
        
        # Usar export_file directamente para obtener el PDF, esto funciona tanto para GDocs como para PDFs ya existentes.
        sow_bytes = self.drive.export_file(sow_file_id, mime_type='application/pdf')

        sow_filename = "sow.pdf"
        try:
            with open(sow_filename, 'wb') as f:
                f.write(sow_bytes)
            print(f"    - SOW PDF downloaded as '{sow_filename}'.")

            # Use the orchestrator's new method for processing the PDF
            gemini_sow_parts = self.gemini.process_file_for_gemini(
                file_path=sow_filename,
                mime_type='application/pdf'
            )

            # If in Developer API mode, track for cleanup
            if not self.gemini.is_vertex_ai_mode():
                for part in gemini_sow_parts:
                    if isinstance(part, types.File):
                        self.uploaded_files_to_track.append(part.name)

            return gemini_sow_parts
        except Exception as e:
            print(f"  ❌ ERROR in _prepare_sow_for_gemini: {e}")
            traceback.print_exc()
            raise
        finally:
            if os.path.exists(sow_filename):
                os.remove(sow_filename)
                print(f"    - Temporary local file '{sow_filename}' deleted.")

    def load(self) -> tuple[str, list, list[str]]:
        """
        Downloads, parses, and processes the knowledge base artifacts.

        Returns:
            A tuple containing:
            - system_instructions (str): The system instructions.
            - final_prompt_sequence (list): The prompt sequence with attachments (List[types.Part]).
            - uploaded_files (list[str]): Gemini resource names for cleanup (only for Dev API).
        """
        print("🧠 Loading knowledge base...")
        system_instructions, prompt_sequence = self._load_and_parse_prompts()
        
        # Process checklist
        gemini_checklist_parts = self._prepare_checklist_for_gemini()
        
        # Process SOW PDF (assuming it's attached to a specific prompt, e.g., Prompt 2)
        gemini_sow_parts = self._prepare_sow_for_gemini()


        # Assemble the final prompt sequence with the attached file(s)
        final_prompt_contents = []
        for prompt_data in prompt_sequence:
            current_prompt_content = [prompt_data['text']]
            if prompt_data['id'] == 1: # Assumes the checklist goes in the first prompt
                current_prompt_content.extend(gemini_checklist_parts)
            # Assuming SOW PDF goes in a specific prompt, e.g., prompt with ID 2
            if prompt_data['id'] == 2:
                current_prompt_content.extend(gemini_sow_parts)
            
            final_prompt_contents.append(current_prompt_content)

        return system_instructions, final_prompt_contents, self.uploaded_files_to_track
