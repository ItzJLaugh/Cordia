import os
import sys
import unittest
from unittest.mock import patch

import psycopg2

os.environ.setdefault("CORDIA_DEV_2FA", "1")
os.environ.setdefault("CORDIA_PG_DSN", "postgresql://test")


class _Cursor:
    def __init__(self, existing):
        self.existing = existing
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement, params=None):
        self.statements.append((statement, params))

    def fetchone(self):
        return (1,) if self.existing else None


class _Connection:
    def __init__(self, existing):
        self.cursor_value = _Cursor(existing)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self.cursor_value


class _SMTP:
    sent = []

    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        pass

    def send_message(self, message):
        self.sent.append(message)


_MISSING = object()
_ORIGINAL_CORDIA_AUTH = sys.modules.get("cordia_auth", _MISSING)
with patch.object(psycopg2, "connect", return_value=_Connection(False)):
    import cordia_auth as auth
if _ORIGINAL_CORDIA_AUTH is _MISSING:
    sys.modules.pop("cordia_auth", None)
else:
    sys.modules["cordia_auth"] = _ORIGINAL_CORDIA_AUTH


class TestAuthEmail(unittest.TestCase):
    def setUp(self):
        _SMTP.sent = []

    def _signup(self, existing):
        connection = _Connection(existing)
        with patch.object(auth, "_conn", return_value=connection), \
                patch.object(auth, "_send_code", return_value=True), \
                patch.object(auth, "_notify_existing"):
            result = auth.signup("person@example.com", "Person", "SecurePass123")
        return result, connection.cursor_value.statements

    def test_signup_response_is_neutral_for_new_and_existing_addresses(self):
        new_result, _ = self._signup(existing=False)
        existing_result, _ = self._signup(existing=True)

        self.assertEqual(new_result[:2], (True, "check your email for next steps"))
        self.assertEqual(existing_result[:2], new_result[:2])

    def test_existing_signup_sends_only_the_existing_account_notice(self):
        connection = _Connection(existing=True)
        with patch.object(auth, "_conn", return_value=connection), \
                patch.object(auth, "_send_code") as send_code, \
                patch.object(auth, "_notify_existing") as notify_existing:
            auth.signup("person@example.com", "Person", "SecurePass123")

        notify_existing.assert_called_once_with("person@example.com")
        send_code.assert_not_called()

    def test_new_signup_sends_a_verification_code_not_an_existing_notice(self):
        connection = _Connection(existing=False)
        with patch.object(auth, "_conn", return_value=connection), \
                patch.object(auth, "_send_code", return_value=True) as send_code, \
                patch.object(auth, "_notify_existing") as notify_existing:
            auth.signup("person@example.com", "Person", "SecurePass123")

        send_code.assert_called_once()
        sent_email, sent_code = send_code.call_args.args
        self.assertEqual(sent_email, "person@example.com")
        self.assertRegex(sent_code, r"^\d{6}$")
        notify_existing.assert_not_called()

    def test_existing_account_notice_says_that_no_code_was_generated(self):
        with patch.dict(os.environ, {
                "GMAIL_USER": "sender@example.com",
                "GMAIL_APP_PASSWORD": "app-password",
        }), patch.object(auth.smtplib, "SMTP", _SMTP):
            auth._notify_existing("person@example.com")

        self.assertEqual(len(_SMTP.sent), 1)
        message = _SMTP.sent[0]
        self.assertEqual(
            message["Subject"],
            "This email already has a Cordia account",
        )
        body = message.get_content()
        self.assertIn("No verification code was generated", body)
        self.assertIn("sign in", body.lower())
        self.assertNotIn("Good evening", body)
        self.assertNotIn("Dr.", body)

    def test_verification_email_contains_the_requested_code_only(self):
        with patch.dict(os.environ, {
                "GMAIL_USER": "sender@example.com",
                "GMAIL_APP_PASSWORD": "app-password",
        }), patch.object(auth.smtplib, "SMTP", _SMTP):
            self.assertTrue(auth._send_code("person@example.com", "482193"))

        self.assertEqual(len(_SMTP.sent), 1)
        message = _SMTP.sent[0]
        self.assertEqual(message["Subject"], "Your Cordia verification code")
        body = message.get_content()
        self.assertIn("482193", body)
        self.assertNotIn("Good evening", body)
        self.assertNotIn("Dr.", body)


if __name__ == "__main__":
    unittest.main()
