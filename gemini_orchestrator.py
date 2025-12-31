import google.genai as genai # pyright: ignore[reportMissingImports]
import os
import mimetypes
import traceback # Import traceback for detailed error logging
from google.genai import types, chats # pyright: ignore[reportMissingImports]
from typing import Optional, List, Union
from retry_on_gemini_error import retry_on_gemini_error
from pdf_splitter_helper import PdfSplitterHelper # Import the new helper

class GeminiOrchestrator:
    """
    Orchestration class to interact with the Google Gemini API using the new SDK.

    It encapsulates client initialization, model configuration, file handling, and
    prompt execution, following an object-oriented design to maximize
    reusability and clarity.
    """

    chat: Optional[chats.Chat] = None
    pdf_splitter: PdfSplitterHelper = None

    def __init__(self, api_key: str = None, project_id: str = None, location: str = None):
        """
        Class constructor. Initializes the Gemini client.

        Args:
            api_key (str, optional): The API key for Gemini.
            project_id (str, optional): The Google Cloud Project ID for Vertex AI. If provided,
                                        enables Vertex AI mode.
            location (str, optional): The GCP region for Vertex AI. Defaults to "us-central1" if
                                      project_id is provided and location is None.

        Raises:
            ValueError: If the API key is not provided (for Developer mode) or project_id is missing (for Vertex mode).
        """
        # Determine if using Vertex AI mode based on project_id presence
        use_vertex_ai_mode = False
        if project_id:
            use_vertex_ai_mode = True
            print(f"ℹ️ Project ID '{project_id}' provided. Initializing in Vertex AI mode.")
            if not location:
                location = "us-central1" # Default location for Vertex AI if not specified
                print(f"ℹ️ Defaulting Vertex AI location to '{location}' as none was provided.")

        # Initialize the genai.Client
        if use_vertex_ai_mode:
            if api_key:
                print("ℹ️ API Key provided for Vertex AI mode. Initializing client with API Key and Location (Project ID inferred from key/env to avoid mutual exclusion error).")
                # Vertex AI with API Key: Pass vertexai=True, api_key, and location.
                # IMPORTANT: Passing 'project' along with 'api_key' causes a ValueError in the SDK.
                # We rely on the API Key or environment variables for the project context.
                self.client = genai.Client(
                    vertexai=True,
                    api_key=api_key
                    # Removed 'location' parameter to avoid ValueError.
                    # Relying on GOOGLE_CLOUD_LOCATION environment variable for location context.
                )
            else:
                print("ℹ️ No API Key provided for Vertex AI mode. Initializing with Project ID and Location (relying on ADC).")
                self.client = genai.Client(
                    vertexai=True,
                    project=project_id,
                    location=location
                )
            print(f"✅ Gemini Client initialized in Vertex AI mode.")
        else: # Developer API mode
            if not api_key:
                 raise ValueError("API Key is required for Developer API mode (no project_id provided).")
            
            self.client = genai.Client(api_key=api_key)
            print("✅ Gemini Client initialized in Developer API mode.")

        print(f"DEBUG: Final client mode: {'Vertex AI' if self.is_vertex_ai_mode() else 'Developer API'}")
        
        self.pdf_splitter = PdfSplitterHelper() # Initialize the PDF splitter

        # Attributes for model parameters and chat history
        self.model_name = None
        self.system_instruction = None
        self.generation_config = None
        self.safety_settings = None
        self.tools = None
        self.tool_config = None

    def is_vertex_ai_mode(self) -> bool:
        """
        Determines if the Gemini client is configured for Vertex AI.
        It checks the 'vertexai' attribute of the underlying genai.Client.
        """
        return getattr(self.client, 'vertexai', False)

    def initialize_model_parameters(self, model_name: str, system_instruction: str, temperature: float = 0.2,
                                    enable_google_search: bool = False, enable_code_execution: bool = False,
                                    enable_thinking: bool = False, thinking_budget: int = 4096):
        """
        Initializes the configuration parameters for the generative model.

        Args:
            model_name (str): The name of the generative model to use (e.g., "gemini-1.5-pro-latest").
            system_instruction (str): The system prompt that defines the model's behavior.
            temperature (float, optional): The temperature for content generation. Defaults to 0.2.
            enable_google_search (bool, optional): If True, enables the `GoogleSearchRetrieval` tool. Defaults to False.
            enable_code_execution (bool, optional): If True, enables the `CodeExecution` tool. Defaults to False.
            enable_thinking (bool, optional): If True, enables the model's thinking/reasoning capabilities. Defaults to False.
            thinking_budget (int, optional): The token budget for thinking. Defaults to 4096.
        """
        self.model_name = model_name
        self.system_instruction = system_instruction
        self.generation_config = {"temperature": temperature}

        # Configure Thinking (Reasoning) mode
        if enable_thinking:
            self.generation_config["thinking_config"] = {
                "include_thoughts": False, # Changed to False for silent thinking
                "thinking_budget": thinking_budget
            }
            print(f"  🧠 Thinking mode enabled (Budget: {thinking_budget} tokens).")

        # Safety settings using string identifiers
        self.safety_settings = [
            {'category': 'HARM_CATEGORY_HARASSMENT', 'threshold': 'BLOCK_NONE'},
            {'category': 'HARM_CATEGORY_HATE_SPEECH', 'threshold': 'BLOCK_NONE'},
            {'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'threshold': 'BLOCK_NONE'},
            {'category': 'HARM_CATEGORY_DANGEROUS_CONTENT', 'threshold': 'BLOCK_NONE'},
        ]

        # Configure tools
        tools = []
        if enable_google_search:
            tools.append("google_search_retrieval")
            print("  - Google Search tool enabled.")

        if enable_code_execution:
            tools.append("code_execution")
            print("  - Code Execution tool enabled.")
        self.tools = tools

        # The new SDK handles file and URL processing automatically when files are provided
        # in the prompt, so explicit FileProcessingConfig is no longer needed for this basic use case.
        self.tool_config = None
        
        print(f"✅ Model '{model_name}' parameters initialized.")

    def start_chat_session(self):
        """
        Starts a new chat session with an empty history.
        """
        if not self.model_name:
            raise RuntimeError("The model has not been initialized. Call 'initialize_model_parameters' first.")

        config = {
            'system_instruction': self.system_instruction,
            'safety_settings': self.safety_settings,
            'tools': self.tools,
            'tool_config': self.tool_config
        }
        if self.generation_config:
            config.update(self.generation_config)

        self.chat = self.client.chats.create(
            model=self.model_name,
            history=[], # Start with an empty history
            config=config
        )
        print("✅ New chat session started.")

    def prime_chat_context(self, prompt_sequence: list):
        """
        Primes the chat session by sending an initial sequence of prompts and
        capturing their responses to build context.
        """
        if not self.chat:
            raise RuntimeError("Chat session not started. Call 'start_chat_session' first.")
        
        if not prompt_sequence:
            print("🟡 No prompt sequence provided for priming. Skipping.")
            return

        print("🧠 Priming chat context with prompt sequence...")
        for i, prompt_parts in enumerate(prompt_sequence):
            print(f"  - Executing priming step {i+1}/{len(prompt_sequence)}...")
            self.send_message(prompt_parts, verbose=False) # Call in silent mode
        print("✅ Chat context primed successfully.")

    @retry_on_gemini_error()
    def process_file_for_gemini(self, file_path: str, mime_type: str) -> List[types.Part]:
        """
        Processes a local file for inclusion in a Gemini prompt, adapting to
        either Developer API (via files.upload) or Vertex AI (via inline data/splitting).

        Args:
            file_path (str): The path to the local file.
            mime_type (str): The MIME type of the file.

        Returns:
            List[types.Part]: A list of types.Part objects representing the file(s) or its fragments,
                              ready to be included in a prompt. Returns a list for consistency.

        Raises:
            ValueError: If the file is too large for current configuration or unsupported type.
        """
        print(f"⚙️ Processing file '{file_path}' (MIME: {mime_type}) for Gemini prompt...")
        
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

        if self.is_vertex_ai_mode():
            print("  ⚡ Vertex AI mode detected. Using inline data strategy.")
            if mime_type == "application/pdf":
                if file_size_mb > self.pdf_splitter.MAX_TOTAL_SIZE_MB:
                    raise ValueError(
                        f"PDF file '{file_path}' ({(file_size_mb):.2f} MB) exceeds maximum allowed size "
                        f"of {self.pdf_splitter.MAX_TOTAL_SIZE_MB} MB for Vertex AI inline processing."
                    )
                
                # Split PDF into chunks
                pdf_fragments_data = self.pdf_splitter.split_pdf(file_path)
                
                # Convert byte fragments to types.Part objects
                parts = []
                for fragment_bytes, fragment_name in pdf_fragments_data:
                    parts.append(types.Part.from_bytes(data=fragment_bytes, mime_type="application/pdf"))
                    print(f"  - Added PDF fragment '{fragment_name}' as inline data.")
                return parts

            else: # For other file types in Vertex AI (e.g., CSV, text, images)
                # Read bytes for inline data
                with open(file_path, 'rb') as f:
                    file_bytes = f.read()
                print(f"  - Added file as inline data (Size: {file_size_mb:.2f} MB).")
                return [types.Part.from_bytes(data=file_bytes, mime_type=mime_type)]
        else: # Developer API mode
            print("  🚀 Developer API mode detected. Using files.upload strategy.")
            if mime_type == "application/pdf" and file_size_mb > self.pdf_splitter.MAX_TOTAL_SIZE_MB:
                 print(f"  ⚠️ Warning: PDF file '{file_path}' ({(file_size_mb):.2f} MB) is large. "
                       f"Gemini Developer API files.upload will be used.")

            uploaded_file = self.client.files.upload(file=file_path)
            # self.uploaded_files_to_track.append(uploaded_file.name) # This tracking will be handled by KnowledgeBaseLoader
            print(f"✅ File uploaded to Gemini Developer API. Resource: '{uploaded_file.name}'")
            return [uploaded_file] # Return as a list for consistency with Vertex AI path

    def upload_file(self, file_path: str, mime_type: Optional[str] = None) -> List[types.Part]:
        """
        Public entrypoint for file uploads. Routes to process_file_for_gemini.
        The return type is unified to List[types.Part] for flexibility.
        """
        if mime_type is None:
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type is None:
                raise ValueError(f"Could not determine MIME type for {file_path}. Please provide it.")
        
        return self.process_file_for_gemini(file_path, mime_type)

    @retry_on_gemini_error()
    def delete_gemini_developer_api_file(self, file_name: str):
        """
        Deletes a file from the Gemini Developer API service using its resource name.
        This method is only for files uploaded via the Developer API's File Service.

        Args:
            file_name (str): The resource name of the file (e.g., 'files/xxxx').
        """
        print(f"🗑️ Deleting Gemini Developer API file resource: '{file_name}'...")
        if self.is_vertex_ai_mode():
            print("  ⚠️ Skipping Developer API file deletion: Currently in Vertex AI mode. Files are inline and not managed by Gemini File Service.")
            return

        try:
            self.client.files.delete(name=file_name)
            print("✅ Resource deleted successfully.")
        except Exception as e:
            print(f"⚠️ Could not delete resource '{file_name}'. Error: {e}")
            traceback.print_exc()

    def delete_file(self, file_name: str):
        """
        Alias for delete_gemini_developer_api_file for backward compatibility.
        """
        return self.delete_gemini_developer_api_file(file_name)

    # The existing upload_file, delete_file, get_file_metadata methods are now integrated into process_file_for_gemini

    @retry_on_gemini_error()
    def get_file_metadata(self, file_name: str) -> types.File:
        """
        Gets the metadata of a file uploaded to the Gemini Developer API service.
        This method is only for Developer API files.

        Args:
            file_name (str): The resource name of the file (e.g., 'files/xxxx').

        Returns:
            types.File: An object with the file's metadata.
        """
        print(f"ℹ️ Getting metadata for: '{file_name}' (Developer API file service)...")
        if self.is_vertex_ai_mode():
            print("  ⚠️ Skipping Developer API file metadata: Currently in Vertex AI mode. Files are inline and not managed by Gemini File Service.")
            raise RuntimeError("Cannot get metadata for Developer API files in Vertex AI mode.")
        
        file_object = self.client.files.get(name=file_name)
        print("✅ Metadata obtained.")
        return file_object

    def create_file_part_from_bytes(self, file_bytes: bytes, mime_type: str) -> types.Part:
        """
        Creates a `types.Part` object from in-memory byte content.

        This is useful for creating prompt parts from file content that has been
        downloaded or generated without saving it to disk first.

        Args:
            file_bytes (bytes): The binary content of the file.
            mime_type (str): The MIME type of the content (e.g., 'application/pdf').

        Returns:
            types.Part: A part object ready to be included in a prompt.
        """
        return types.Part.from_bytes(data=file_bytes, mime_type=mime_type)

    @retry_on_gemini_error()
    def send_message(self, prompt_parts: list, verbose: bool = True) -> str:
        """
        Sends a message (which can include text and files) and updates the chat history.

        Args:
            prompt_parts (list): A list of message parts.
                                 E.g., ["Analyze this file:", uploaded_file_object]
            verbose (bool): If True, prints status messages to the console.

        Returns:
            str: The model's text response.

        Raises:
            RuntimeError: If there is no active chat session.
        """
        if self.chat is None:
            raise RuntimeError("No active chat session. Call 'start_chat_session' first.")

        if verbose:
            print("➡️ Sending message to the model for analysis...")
        
        response = self.chat.send_message(prompt_parts)
        
        if verbose:
            print("⬅️ Response received.")
            print("Gemini response:", response.text)

        return response.text