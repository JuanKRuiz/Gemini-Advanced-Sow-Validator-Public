import os
import sys
import traceback

from gemini_orchestrator import GeminiOrchestrator
from google_drive_helper import GoogleDriveHelper
from google_sheets_helper import GoogleSheetsHelper
from sow_review_orchestrator import SowReviewOrchestrator

# Conditional imports for authentication helpers
# These are moved here to facilitate Colab workflow where classes might be copied to cells
# and imports should be at the top of the file.
from colab_auth_helper import ColabAuthHelper # type: ignore[attr-defined]
from local_auth_helper import LocalAuthHelper # type: ignore[attr-defined]

# --- Application Configuration Constants ---
# (Moved to initializer parameters)

class Application:
    """
    Encapsulates the entire application logic, from configuration and
    authentication to the execution of the SoW review workflow.
    """
    def __init__(self, environment: str = 'colab', 
                 prompt_url: str = None, 
                 checklist_url: str = None, 
                 template_url: str = None,
                 target_sheet_name: str = "Checklist Template",
                 start_cell: str = "B26",
                 gemini_model_name: str = "gemini-3-pro-preview"):
        """
        Initializes the application for a specific environment.

        Args:
            environment (str): The execution environment ('colab' or 'local').
            prompt_url (str): URL to the system prompt.
            checklist_url (str): URL to the validation checklist.
            template_url (str): URL to the report template.
            target_sheet_name (str): Name of the sheet to write to.
            start_cell (str): Starting cell for writing data.
            gemini_model_name (str): Gemini model to use.
        """
        self.env = environment
        self.credentials = None
        self.gemini_api_key = None
        self.project_id = None
        self.location = None
        
        # Configuration
        self.config = {
            "prompt_url": prompt_url,
            "checklist_url": checklist_url,
            "template_url": template_url,
            "target_sheet_name": target_sheet_name,
            "start_cell": start_cell,
            "gemini_model_name": gemini_model_name
        }
        
        # Validate critical config
        if not all([prompt_url, checklist_url, template_url]):
             raise ValueError("Missing critical configuration: prompt_url, checklist_url, and template_url are required.")

    def _load_config(self) -> dict:
        """Loads the configuration (Deprecated/Pass-through)."""
        print("✅ Configuration loaded.")
        return self.config

    def _authenticate(self):
        """Handles authentication based on the environment."""
        if self.env == 'colab':
            # `ColabAuthHelper` is imported at the top now
            auth_helper = ColabAuthHelper()
            self.credentials = auth_helper.authenticate()
            self.gemini_api_key = auth_helper.get_secret('GEMINI_API_KEY')
            # Attempt to get Vertex AI config from secrets
            try:
                self.project_id = auth_helper.get_secret('GOOGLE_CLOUD_PROJECT')
                self.location = auth_helper.get_secret('GOOGLE_CLOUD_LOCATION')
            except Exception:
                # Secrets might not exist if not using Vertex, that's fine.
                pass
                
        elif self.env == 'local':
            # `LocalAuthHelper` is imported at the top now
            auth_helper = LocalAuthHelper() # Uses default scopes and file paths
            # NOTE: For local execution, GEMINI_API_KEY should be set as an environment variable.
            self.gemini_api_key = os.environ.get('GEMINI_API_KEY')
            self.project_id = os.environ.get('GOOGLE_CLOUD_PROJECT')
            self.location = os.environ.get('GOOGLE_CLOUD_LOCATION')
            self.credentials = auth_helper.authenticate()
        else:
            raise ValueError(f"Unsupported environment: {self.env}")

        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not found. Please configure it in Colab secrets or as an environment variable.")

    def run(self, sow_url: str):
        """
        Executes the main SoW validation workflow.
        """
        print("\n" + "="*50)
        print("🚀 STARTING SOW VALIDATION PROCESS 🚀")
        print("="*50)

        try:
            self._authenticate()

            if not self.credentials or not self.gemini_api_key:
                raise RuntimeError("Authentication failed. Cannot proceed.")

            self.config['sow_url'] = sow_url

            # Dependency Injection
            # Now passing project_id and location to support Vertex AI mode inference
            gemini_orchestrator = GeminiOrchestrator(
                api_key=self.gemini_api_key,
                project_id=self.project_id,
                location=self.location
            )
            drive_helper = GoogleDriveHelper(credentials=self.credentials)
            sheets_helper = GoogleSheetsHelper(credentials=self.credentials)
            print("✅ API helpers initialized.")

            # Main Orchestrator Execution
            sow_orchestrator = SowReviewOrchestrator(gemini_orchestrator, drive_helper, sheets_helper, self.config)
            final_report_url = sow_orchestrator.run()

            # Display Final Result
            if final_report_url:
                print("\n" + "★" * 60)
                print("   🎉  SOW VALIDATION SUCCESSFULLY COMPLETED!  🎉")
                print("★" * 60)
                print("\n📄  Report Generated Successfully:")
                print(f"    🔗  {final_report_url}")
                print("\n🚀  Next Steps:")
                print("    1. Click the link above to open the Google Sheet.")
                print("    2. Review the 'Checklist Template' tab for the detailed analysis.")
                print("    3. Check the 'System Instructions' tab if available for context.")
                print("\n💡  Powered by Gemini 3 Pro (Thinking Mode)")
                print("=" * 60 + "\n")
            else:
                print("\n" + "="*50)
                print("🟡 The process finished but no report URL was generated. Please review the logs for details.")
                print("="*50)

        except Exception as e:
            print(f"\n🚨 FATAL ERROR DURING EXECUTION: {e}")
            traceback.print_exc()