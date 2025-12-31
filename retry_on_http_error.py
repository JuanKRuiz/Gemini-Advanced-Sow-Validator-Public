#@title Retry Decorator for API Calls

import time
import random
from functools import wraps
from googleapiclient.errors import HttpError

def retry_on_http_error(max_retries=5, backoff_factor=1.0):
    """
    Decorator that implements exponential backoff with jitter for transient HttpErrors.
    It will only retry on server-side errors (5xx).
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except HttpError as e:
                    # Retry only on server-side errors (5xx)
                    if e.resp.status >= 500:
                        retries += 1
                        if retries >= max_retries:
                            raise  # Re-raise the last exception if max retries are exceeded
                        sleep_time = (backoff_factor * (2 ** (retries - 1))) + (random.uniform(0, 1))
                        print(f"⚠️ API call failed with status {e.resp.status}. Retrying in {sleep_time:.2f}s... ({retries}/{max_retries})")
                        time.sleep(sleep_time)
                    else:
                        raise # Do not retry on client-side errors (4xx)
        return wrapper
    return decorator