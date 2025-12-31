from googleapiclient.discovery import build
from retry_on_http_error import retry_on_http_error
import httplib2
import google_auth_httplib2 # Essential import for AuthorizedHttp

class GoogleSheetsHelper:
    """
    Helper class to encapsulate Google Sheets API v4 operations.

    Focuses on writing data to spreadsheets.
    """

    def __init__(self, credentials, timeout: int = 60):
        """
        Initializes the helper with Google credentials.

        Args:
            credentials: Google authentication credentials object.
            timeout (int): Timeout in seconds for HTTP requests. Defaults to 60.
        """
        if not credentials:
            raise ValueError("Credentials are required to initialize GoogleSheetsHelper.")
        
        # Create a custom httplib2.Http instance with a defined timeout
        http_client = httplib2.Http(timeout=timeout)
        
        # Use google_auth_httplib2.AuthorizedHttp to wrap the credentials and the http client
        # This is the correct way to use google-auth credentials with a custom httplib2 instance
        authorized_http = google_auth_httplib2.AuthorizedHttp(credentials, http=http_client)
        
        # Pass the authorized http client to build
        self.service = build('sheets', 'v4', http=authorized_http)
        print("✅ Google Sheets service initialized.")

    @retry_on_http_error()
    def write_data(self, sheet_id: str, sheet_name: str, start_cell: str, data: list):
        """
        Writes a data matrix (list of lists) to a spreadsheet.

        Args:
            sheet_id (str): The ID of the target spreadsheet.
            sheet_name (str): The name of the tab within the spreadsheet.
            start_cell (str): The starting cell where the data will be pasted (e.g., "A1").
            data (list): A list of lists representing the rows and columns to write.
        """
        range_to_update = f"'{sheet_name}'!{start_cell}"
        body = {'values': data}
        self.service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=range_to_update,
            valueInputOption='USER_ENTERED',
            body=body
        ).execute()