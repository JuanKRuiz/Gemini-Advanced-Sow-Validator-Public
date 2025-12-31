import io
import re
import httplib2
import google_auth_httplib2 # Essential import for AuthorizedHttp
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from retry_on_http_error import retry_on_http_error

class GoogleDriveHelper:
    """
    Helper class to encapsulate Google Drive API v3 operations.

    Manages downloading, exporting, copying, and managing files and folders.
    It is environment-agnostic and receives credentials for its operation.
    """

    def __init__(self, credentials, timeout: int = 60):
        """
        Initializes the helper with Google credentials.

        Args:
            credentials (google.auth.credentials.Credentials): Google authentication
                credentials object.
            timeout (int): Timeout in seconds for HTTP requests. Defaults to 60.
        """
        if not credentials:
            raise ValueError("Credentials are required to initialize GoogleDriveHelper.")
        
        # Create a custom httplib2.Http instance with a defined timeout
        http_client = httplib2.Http(timeout=timeout)
        
        # Use google_auth_httplib2.AuthorizedHttp to wrap the credentials and the http client
        # This is the correct way to use google-auth credentials with a custom httplib2 instance
        authorized_http = google_auth_httplib2.AuthorizedHttp(credentials, http=http_client)
        
        # Pass the authorized http client to build. 
        # Do NOT pass 'credentials' again.
        self.service = build('drive', 'v3', http=authorized_http)
        print("✅ Google Drive service initialized.")

    def get_id_from_url(self, url: str) -> str | None:
        """
        Extracts the file ID from a Google Workspace URL.

        Args:
            url (str): The full URL of the Google Drive, Doc, or Sheet file.

        Returns:
            str | None: The extracted file ID or None if not found.
        """
        match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
        if match:
            return match.group(1)
        match = re.search(r'id=([a-zA-Z0-9_-]+)', url)
        if match:
            return match.group(1)
        return None

    @retry_on_http_error()
    def _download_media(self, request) -> bytes:
        """
        Private method to handle content download from an API request.

        Args:
            request (googleapiclient.http.HttpRequest): The executable API request
                (e.g., service.files().get_media() or service.files().export_media()).

        Returns:
            bytes: The binary content of the downloaded file.
        """
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        return fh.getvalue()

    @retry_on_http_error()
    def download_file_content(self, file_id: str) -> bytes:
        """
        Downloads the binary content of a Drive file (e.g., a text file).

        Args:
            file_id (str): The ID of the file to download.
        """
        request = self.service.files().get_media(fileId=file_id)
        return self._download_media(request)

    @retry_on_http_error()
    def export_file(self, file_id: str, mime_type: str) -> bytes:
        """
        Exports a native Google file (Doc, Sheet) to a specific format.

        Args:
            file_id (str): The ID of the Google file to export.
            mime_type (str): The MIME type of the target format (e.g., 'application/pdf', 'text/csv').

        Returns:
            bytes: The content of the exported file.
        """
        request = self.service.files().export_media(fileId=file_id, mimeType=mime_type)
        return self._download_media(request)

    @retry_on_http_error()
    def find_or_create_folder(self, folder_name: str, parent_id: str | None = None) -> str:
        """
        Finds a folder by name within a parent folder (or in the root).
        If not found, it creates it.

        Args:
            folder_name (str): The name of the folder to find or create.
            parent_id (str | None, optional): The ID of the parent folder.
                                               If None, it searches/creates in the root.

        Returns:
            str: The ID of the found or created folder.
        """
        parent_query = f"and '{parent_id}' in parents" if parent_id else "and 'root' in parents"
        q = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false {parent_query}"

        results = self.service.files().list(q=q, fields="files(id)", spaces="drive", supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
        items = results.get('files', [])

        if items:
            return items[0].get('id')
        else:
            folder_metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
            if parent_id:
                folder_metadata['parents'] = [parent_id]
            folder = self.service.files().create(body=folder_metadata, fields='id').execute()
            return folder.get('id')

    @retry_on_http_error()
    def copy_file(self, source_file_id: str, dest_folder_id: str, new_title: str) -> str:
        """
        Copies a file to a destination folder with a new title.

        Args:
            source_file_id (str): The ID of the file to copy.
            dest_folder_id (str): The ID of the destination folder.
            new_title (str): The new name for the copied file.

        Returns:
            str: The ID of the new copied file.
        """
        copy_body = {'name': new_title, 'parents': [dest_folder_id]}
        new_file = self.service.files().copy(fileId=source_file_id, body=copy_body, fields='id').execute()
        return new_file.get('id')

    @retry_on_http_error()
    def get_file_metadata(self, file_id: str, fields: str = 'name') -> dict:
        """
        Gets specific metadata for a file by its ID.

        Args:
            file_id (str): The ID of the file.
            fields (str): String with the fields to retrieve, separated by commas
                          (e.g., 'name, id, parents'). Defaults to 'name'.

        Returns:
            dict: The file's metadata.
        """
        return self.service.files().get(fileId=file_id, fields=fields).execute()