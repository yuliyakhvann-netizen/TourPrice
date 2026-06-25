from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.exceptions import OperatorLoginError, OperatorSearchError, SessionExpiredError

# Retry for network-level errors during search (not login)
retry_on_search_error = retry(
    retry=retry_if_exception_type((OperatorSearchError, TimeoutError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    reraise=True,
)

# Retry for login — fewer attempts, longer wait
retry_on_login_error = retry(
    retry=retry_if_exception_type((OperatorLoginError, TimeoutError)),
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=5, min=5, max=60),
    reraise=True,
)

# Retry when session expires mid-search
retry_on_session_expired = retry(
    retry=retry_if_exception_type(SessionExpiredError),
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
