from http.cookies import SimpleCookie

import pytest
from starlette.responses import Response

from financito.config import settings
from financito.security import create_session
from financito.services.documents import safe_path


def test_vault_accepts_inside_and_rejects_outside():
    inside=settings.vault_dir/"inside.txt"; inside.write_text("ok"); assert safe_path(inside)==inside.resolve()
    outside=settings.data_dir.parent/"financito-outside-test.txt"; outside.write_text("secret")
    try:
        with pytest.raises(ValueError): safe_path(outside)
    finally: outside.unlink(missing_ok=True)


def test_create_session_reuses_valid_cookie_and_csrf_token():
    first_response=Response()
    first=create_session(first_response)
    cookies=SimpleCookie()
    cookies.load(first_response.headers["set-cookie"])
    signed_cookie=cookies["financito_session"].value

    second_response=Response()
    second=create_session(second_response,signed_cookie)

    assert second["csrf_token"]==first["csrf_token"]
    assert "set-cookie" not in second_response.headers
