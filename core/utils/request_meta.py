def get_client_ip(request) -> str | None:
    """First IP in X-Forwarded-For if set (trust the proxy header in prod), else REMOTE_ADDR."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip() or None
    return request.META.get('REMOTE_ADDR') or None


def get_user_agent(request) -> str:
    """Truncated to 300 chars to fit our CharField."""
    return (request.META.get('HTTP_USER_AGENT') or '')[:300]
