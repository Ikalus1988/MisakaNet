```python
import unittest
from email.parser import BytesParser
from email.policy import default
from email import message_from_bytes
from email.header import decode_header
from email.utils import parseaddr
import base64

class TestEmailUtils(unittest.TestCase):

    def test_deeply_nested_multipart(self):
        # multipart/mixed containing multipart/alternative
        email_data = """\
From: sender@example.com
To: recipient@example.com
Subject: Test Email
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="boundary"

--boundary
Content-Type: multipart/alternative; boundary="boundary2"

--boundary2
Content-Type: text/plain

Hello World!

--boundary2
Content-Type: text/html

<html>Hello World!</html>

--boundary2--
--boundary--
"""
        parser = BytesParser(policy=default)
        email = parser.parsebytes(email_data.encode())
        self.assertEqual(email['Subject'], 'Test Email')
        self.assertEqual(email['From'], 'sender@example.com')
        self.assertEqual(email['To'], 'recipient@example.com')

    def test_base64_content_transfer_encoding(self):
        # Base64 `Content-Transfer-Encoding` in text/plain part
        email_data = """\
From: sender@example.com
To: recipient@example.com
Subject: Test Email
MIME-Version: 1.0
Content-Type: text/plain; charset="utf-8"; content-transfer-encoding="base64"

SGVsbG8gV29ybGQh
"""
        parser = BytesParser(policy=default)
        email = parser.parsebytes(email_data.encode())
        self.assertEqual(email['Subject'], 'Test Email')
        self.assertEqual(email['From'], 'sender@example.com')
        self.assertEqual(email['To'], 'recipient@example.com')

    def test_missing_content_type(self):
        # Missing `Content-Type` header (should default to text/plain)
        email_data = """\
From: sender@example.com
To: recipient@example.com
Subject: Test Email
MIME-Version: 1.0

Hello World!
"""
        parser = BytesParser(policy=default)
        email = parser.parsebytes(email_data.encode())
        self.assertEqual(email['Subject'], 'Test Email')
        self.assertEqual(email['From'], 'sender@example.com')
        self.assertEqual(email['To'], 'recipient@example.com')

    def test_broken_boundary(self):
        # Broken or missing boundary (should not throw)
        email_data = """\
From: sender@example.com
To: recipient@example.com
Subject: Test Email
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="boundary"

--boundary
Content-Type: text/plain

Hello World!
"""
        parser = BytesParser(policy=default)
        email = parser.parsebytes(email_data.encode())
        self.assertEqual(email['Subject'], 'Test Email')
        self.assertEqual(email['From'], 'sender@example.com')
        self.assertEqual(email['To'], 'recipient@example.com')

    def test_non_ascii_subject(self):
        # Subject line with CJK characters (e.g. `=?UTF-8?B?...?=` encoded subject)
        email_data = """\
From: sender@example.com
To: recipient@example.com
Subject: =?UTF-8?B?...?=
MIME-Version: 1.0
Content-Type: text/plain; charset="utf-8"
"""
        parser = BytesParser(policy=default)
        email = parser.parsebytes(email_data.encode())
        self.assertEqual(email['Subject'], decode_header(email['Subject'])[0][0])
        self.assertEqual(email['From'], 'sender@example.com')
        self.assertEqual(email['To'], 'recipient@example.com')

    def test_non_ascii_body(self):
        # Body with mixed Chinese + English content
        email_data = """\
From: sender@example.com
To: recipient@example.com
Subject: Test Email
MIME-Version: 1.0
Content-Type: text/plain; charset="utf-8"

Hello "" (Chinese characters)
World!
"""
        parser = BytesParser(policy=default)
        email = parser.parsebytes(email_data.encode())
        self.assertEqual(email['Subject'], 'Test Email')
        self.assertEqual(email['From'], 'sender@example.com')
        self.assertEqual(email['To'], 'recipient@example.com')

    def test_non_ascii_sender(self):
        # Sender name with non-ASCII characters
        email_data = """\
From: "" (Chinese characters) sender@example.com
To: recipient@example.com
Subject: Test Email
MIME-Version: 1.0
Content-Type: text/plain; charset="utf-8"
"""
        parser = BytesParser(policy=default)
        email = parser.parsebytes(email_data.encode())
        self.assertEqual(email['Subject'], 'Test Email')
        self.assertEqual(email['From'], parseaddr(email['From'])[1])
        self.assertEqual(email['To'], 'recipient@example.com')

    def test_original_message_separator(self):
        # `Original Message` separator (Outlook-style)
        email_data = """\
From: sender@example.com
To: recipient@example.com
Subject: Test Email
MIME-Version: 1.0
Content-Type: text/plain; charset="utf-8"

Hello World!

Original Message

Hello World!
"""
        parser = BytesParser(policy=default)
        email = parser.parsebytes(email_data.encode())
        self.assertEqual(email['Subject'], 'Test Email')
        self.assertEqual(email['From'], 'sender@example.com')
        self.assertEqual(email['To'], 'recipient@example.com')

    def test_multiple_levels_of_quoting(self):
        # Multiple levels of `>` quoting
        email_data = """\
From: sender@example.com
To: recipient@example.com
Subject: Test Email
MIME-Version: 1.0
Content-Type: text/plain; charset="utf-8"

> > Hello World!
"""
        parser = BytesParser(policy=default)
        email = parser.parsebytes(email_data.encode())
        self.assertEqual(email['Subject'], 'Test Email')
        self.assertEqual(email['From'], 'sender@example.com')
        self.assertEqual(email['To'], 'recipient@example.com')

if __name__ == '__main__':
    unittest.main()
```