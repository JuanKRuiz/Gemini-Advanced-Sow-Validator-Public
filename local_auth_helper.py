import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

class LocalAuthHelper:
    """
    Encapsulates the user authentication flow for a local environment.

    This class is an 'adapter' for a desktop environment. Its sole
    responsibility is to authenticate the user and provide a valid
    credentials object. It exposes the same interface as ColabAuthHelper
    to allow for interchangeability.
    """

    def __init__(self, scopes: list[str] | None = None, client_secrets_path: str = "client_secrets.json", token_path: str = "token.json"):
        """
        Initializes the helper with the configuration for the local OAuth 2.0 flow.

        Args:
            scopes (list[str] | None, optional): List of permissions (scopes) that the application will request.
                                                 If None, it will use the defaults for Drive and Sheets.
                                                 Defaults to None.
            client_secrets_path (str, optional): Path to the client_secrets.json file. Defaults to "client_secrets.json".
            token_path (str, optional): Path where the token.json will be saved to persist the session. Defaults to "token.json".
        """
        if scopes is None:
            self.scopes = [
                "https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/spreadsheets",
            ]
        else:
            self.scopes = scopes

        self.client_secrets_file = client_secrets_path
        self.token_file = token_path
        self.creds = None

    def authenticate(self) -> Credentials:
        """
        Executes the local user authentication flow.

        Searches for a valid token. If it doesn't exist or has expired, it starts
        a browser-based flow for the user to grant consent.

        Returns:
            google.oauth2.credentials.Credentials: The obtained credentials object.
        """
        # The token.json file stores the user's access and refresh tokens.
        if os.path.exists(self.token_file):
            self.creds = Credentials.from_authorized_user_file(self.token_file, self.scopes)

        # If there are no (valid) credentials available, let the user log in.
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                print("♻️ Refreshing access token...")
                self.creds.refresh(Request())
            else:
                print("🚀 Starting new local authentication flow...")
                if not os.path.exists(self.client_secrets_file):
                    raise FileNotFoundError(
                        f"The client secrets file ('{self.client_secrets_file}') was not found. "
                        "Please download it from your Google Cloud Console project."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(self.client_secrets_file, self.scopes)
                # This will open the browser for authentication and consent.
                self.creds = flow.run_local_server(port=0)

            # Save the credentials for the next run.
            with open(self.token_file, 'w') as token:
                token.write(self.creds.to_json())
            print(f"✅ Credentials saved to '{self.token_file}'.")

        print("✅ Local authentication complete. Credentials obtained.")
        return self.creds