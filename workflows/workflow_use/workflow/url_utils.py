"""Redirect-tolerant URL comparison shared by verifiers.

Exact URL equality fails on ordinary server behavior (http->https upgrade,
added locale segments or query params, trailing-slash canonicalization, www.
differences). Navigating to *expected* and landing on such a variant is a
SUCCESSFUL navigation; cross-host redirects still fail.
"""

from urllib.parse import urlparse


def _norm(url: str) -> str:
	return (url or '').split('#')[0].rstrip('/')


def _host(parsed) -> str:
	host = (parsed.netloc or '').lower()
	return host[4:] if host.startswith('www.') else host


def urls_equivalent(current_url: str, expected_url: str) -> bool:
	"""True when *current_url* is *expected_url* or a benign redirect variant of it."""
	if _norm(current_url) == _norm(expected_url):
		return True

	try:
		cur, exp = urlparse(_norm(current_url)), urlparse(_norm(expected_url))
	except ValueError:
		return False

	if not _host(cur) or _host(cur) != _host(exp):
		return False  # landed on a different site: real failure

	cur_path = cur.path.rstrip('/')
	exp_path = exp.path.rstrip('/')
	if cur_path == exp_path:
		return True  # scheme/query/fragment differences are tolerated
	if not exp_path:
		return True  # expected the site root; locale/home redirects are fine
	# Server deepened the path (e.g. /login -> /login/identifier)
	return cur_path.startswith(exp_path + '/')
