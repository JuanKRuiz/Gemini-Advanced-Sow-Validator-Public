import os
import re
import csv
import io
import traceback

from googleapiclient.errors import HttpError

from gemini_orchestrator import GeminiOrchestrator
from google_drive_helper import GoogleDriveHelper
from google_sheets_helper import GoogleSheetsHelper
from knowledge_base_loader import _KnowledgeBaseLoader

class SowReviewOrchestrator:
    """
    Orchestrates the SoW validation workflow, coordinating interactions
    between Gemini, Google Drive, and Google Sheets through their respective helpers.
    """

    def __init__(self, gemini: GeminiOrchestrator, drive: GoogleDriveHelper, sheets: GoogleSheetsHelper, config: dict):
        """
        Initializes the orchestrator with dependencies and configuration.

        Args:
            gemini (GeminiOrchestrator): Helper to interact with Gemini.
            drive (GoogleDriveHelper): Helper to interact with Google Drive.
            sheets (GoogleSheetsHelper): Helper to interact with Google Sheets.
            config (dict): Dictionary with URLs and configuration parameters. Expected keys:
                - 'sow_url' (str): URL of the SoW to be analyzed.
                - 'prompt_url' (str): URL of the prompts file.
                - 'checklist_url' (str): URL of the checklist spreadsheet.
                - 'template_url' (str): URL of the report template spreadsheet.
                - 'target_sheet_name' (str): Name of the tab in the template.
                - 'start_cell' (str): Starting cell for pasting data.
                - 'gemini_model_name' (str): The name of the Gemini model to use.
        """
        self.gemini = gemini
        self.drive = drive
        self.sheets = sheets
        self.config = config
        self.uploaded_gemini_files = []

    def _prepare_gemini_session(self):
        """Phase 1 & 2: Loads the knowledge base and configures the Gemini model."""
        print("\n--- 🚀 Phase 1 & 2: Preparing Gemini Session ---")
        kb_loader = _KnowledgeBaseLoader(self.drive, self.gemini, self.config)
        system_instructions, prompt_sequence, kb_files = kb_loader.load()
        self.uploaded_gemini_files.extend(kb_files)

        self.gemini.initialize_model_parameters(
            model_name=self.config['gemini_model_name'],
            system_instruction=system_instructions,
            temperature=0.1,
            enable_google_search=False, # We are providing all context, no external search needed.
            enable_code_execution=False,
            enable_thinking=True, # Enable Gemini 3.0 Thinking mode
            thinking_budget=8192  # Budget for reasoning tokens
        )
        
        # Start the session (it will be empty)
        self.gemini.start_chat_session()
        
        # Prime the context sequentially
        self.gemini.prime_chat_context(prompt_sequence=prompt_sequence)

        print("✅ Gemini model configured and ready.")

    def _analyze_sow(self) -> str:
        """
        Phase 3: Downloads the SoW content, creates a prompt part from it in memory,
        and sends it to Gemini for analysis.

        Returns:
            str: The text analysis received from the model.
        """
        print("\n--- 🔬 Phase 3: Analyzing the SoW ---")

        sow_id = self.drive.get_id_from_url(self.config['sow_url'])
        if not sow_id:
            raise ValueError("Could not extract ID from the SoW URL.")

        print("  - 📥 Downloading SoW content from Google Drive...")
        sow_bytes = self.drive.export_file(sow_id, mime_type='application/pdf')
        sow_file_part = self.gemini.create_file_part_from_bytes(sow_bytes, mime_type='application/pdf')
        print("  - ✅ SoW content prepared for Gemini in memory.")

        final_prompt_parts = ["Review this Document (including its images):", sow_file_part]
        analysis_text = self.gemini.send_message(final_prompt_parts, verbose=False)
        return analysis_text

    def _generate_report(self, analysis_text: str) -> str:
        """Phase 4: Parses the analysis and generates the report in Google Sheets."""
        print("\n--- 📊 Phase 4: Generating Report in Google Sheets ---")

        tsv_match = re.search(r"```(?:tsv\n)?(.*)```", analysis_text, re.DOTALL)
        if not tsv_match:
            raise ValueError("Could not find the TSV code block in the Gemini response.")
        clean_tsv = tsv_match.group(1).strip()
        data_to_paste = list(csv.reader(io.StringIO(clean_tsv), delimiter='\t'))
        print("✅ TSV result parsed.")

        folder_id = self.drive.find_or_create_folder('Temp')
        print("✅ Destination folder 'Temp' ensured.")

        sow_id = self.drive.get_id_from_url(self.config['sow_url'])
        copy_title = "Checklist - Analyzed SoW"
        # Attempt to get the SoW name to create a descriptive title for the report.
        try:
            sow_metadata = self.drive.get_file_metadata(sow_id, fields='name')
            base_sow_name, _ = os.path.splitext(sow_metadata.get('name'))
            copy_title = f"Checklist - {base_sow_name}"
        except HttpError as e:
            # Provide specific feedback based on the HTTP error code.
            if e.resp.status == 403:
                print(f"⛔️ Permission denied when accessing SoW metadata. Check sharing settings. Using default title.")
            elif e.resp.status == 404:
                print(f"⚠️ SoW file not found when fetching metadata. Using default title.")
            else:
                print(f"⚠️ An HTTP error occurred ({e.resp.status}) while fetching SoW name. Using default title. Error: {e}")
        except Exception as e: # Catch any other unexpected errors.
            print(f"⛔️ An unexpected error occurred while fetching SoW name. Using default title. Error: {e}")

        print(f"Creating spreadsheet with name: '{copy_title}'...")
        template_id = self.drive.get_id_from_url(self.config['template_url'])
        new_sheet_id = self.drive.copy_file(
            source_file_id=template_id,
            dest_folder_id=folder_id,
            new_title=copy_title
        )
        print(f"✅ Spreadsheet created with ID: {new_sheet_id}")

        self.sheets.write_data(
            sheet_id=new_sheet_id,
            sheet_name=self.config['target_sheet_name'],
            start_cell=self.config['start_cell'],
            data=data_to_paste
        )
        print("✅ Data written to the new spreadsheet.")

        final_url = f"https://docs.google.com/spreadsheets/d/{new_sheet_id}/edit"
        return final_url

    def _cleanup(self):
        """Phase 5: Deletes all temporary files uploaded to Gemini."""
        print("\n--- 🧹 Phase 5: Cleaning Up Temporary Resources ---")
        if not self.uploaded_gemini_files:
            print("No Gemini files to clean up.")
            return

        for file_name in self.uploaded_gemini_files:
            self.gemini.delete_file(file_name)

    def run(self) -> str | None:
        """
        Executes the complete SoW validation workflow.
        """
        final_url = None
        try:
            self._prepare_gemini_session()
            analysis_text = self._analyze_sow()
            final_url = self._generate_report(analysis_text)
        except Exception as e:
            print(f"\n🚨 An unexpected error occurred during execution: {e}")
            traceback.print_exc()
        finally:
            self._cleanup()

        return final_url