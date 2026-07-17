from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def _client_ip(request: Request) -> str:
    # Behind nginx/docker every request arrives from the proxy's address, which
    # would make the rate limit global across all users. Key on the last
    # X-Forwarded-For hop: earlier hops are client-supplied (spoofable), but
    # the trusted proxy appends the real client address last.
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=_client_ip)
