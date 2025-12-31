from google.colab import auth, userdata # pyright: ignore[reportMissingImports]
import google.auth

class ColabAuthHelper:
    """
    Encapsulates the user authentication and secret access flow
    specific to Google Colab.

    This class is an 'adapter' for the Colab environment. Its
    responsibility is to authenticate the user, provide a valid
    credentials object, and access Colab secrets.

    NOTE: This class will only work within a Google Colab environment.
    """

    def __init__(self):
        """Initializes the helper. Credentials will be obtained after authentication."""
        self.creds = None

    def authenticate(self) -> google.auth.credentials.Credentials:
        """
        Executes the Colab user authentication flow.

        Returns:
            google.auth.credentials.Credentials: The obtained credentials object.
        """
        print("🚀 Starting Google Colab user authentication...")
        auth.authenticate_user()
        self.creds, _ = google.auth.default()
        print("✅ Authentication complete. Credentials obtained.")
        return self.creds

    def get_secret(self, secret_name: str) -> str | None:
        """
        Gets a secret from the Google Colab secret manager.

        Args:
            secret_name (str): The name of the secret to get (e.g., 'GEMINI_API_KEY').

        Returns:
            str | None: The value of the secret if found, otherwise None.
        """
        print(f"🤫 Accessing Colab secret: '{secret_name}'...")
        try:
            secret_value = userdata.get(secret_name)
            print("✅ Secret obtained successfully.")
            return secret_value
        except userdata.SecretNotFoundError:
            print(f"🚨 Alert: Secret '{secret_name}' not found in Colab's secret manager.")
            return None