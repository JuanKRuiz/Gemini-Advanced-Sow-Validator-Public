#@title Retry Decorator for Gemini API Calls

import time
import random
from functools import wraps
from google.api_core import exceptions as google_api_exceptions

# A tuple of transient exceptions from the google-api-core library.
# These are the errors that are safe to retry.
TRANSIENT_GEMINI_ERRORS = (
    google_api_exceptions.ResourceExhausted,  # 429 Rate Limiting
    google_api_exceptions.InternalServerError, # 500 Server Error
    google_api_exceptions.ServiceUnavailable,  # 503 Service Unavailable
    google_api_exceptions.DeadlineExceeded,    # 504 Gateway Timeout
    google_api_exceptions.Aborted,             # 409 Concurrency Issue
)

def retry_on_gemini_error(max_retries=5, backoff_factor=1.0):
    """
    Decorator that implements exponential backoff with jitter for transient Gemini API errors.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except TRANSIENT_GEMINI_ERRORS as e:
                    retries += 1
                    if retries >= max_retries:
                        raise
                    sleep_time = (backoff_factor * (2 ** (retries - 1))) + (random.uniform(0, 1))
                    print(f"⚠️ Gemini API call failed ({type(e).__name__}). Retrying in {sleep_time:.2f}s... ({retries}/{max_retries})")
                    time.sleep(sleep_time)
        return wrapper
    return decorator