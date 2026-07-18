```python
import unittest
from email import message_from_bytes
from email.header import decode_header
from email.utils import parseaddr
from email.parser import BytesParser
from email.policy import default
from email.errors import MessageParseError
import base64

class TestEmailUtils(unittest.TestCase):

    def test_deeply_nested_multipart(self):
        # Create a deeply nested multipart message
        msg = """
        Content-Type: multipart/mixed; boundary="boundary1"

        --boundary1
        Content-Type: multipart/alternative; boundary="boundary2"

        --boundary2
        Content-Type: text/plain; charset="utf-8"

        Hello, world!

        --boundary2--
        --boundary1--
        """
        msg_bytes = msg.encode('utf-8')
        parser = BytesParser(policy=default)
        msg = parser.parsebytes(msg_bytes)
        self.assertEqual(msg.get_content_type(), 'multipart/mixed')

    def test_base64_content_transfer_encoding(self):
        # Create a message with base64 encoded text/plain part
        msg = """
        Content-Type: text/plain; charset="utf-8"
        Content-Transfer-Encoding: base64

        SGVsbG8sIHdvcmxkIQ==
        """
        msg_bytes = msg.encode('utf-8')
        parser = BytesParser(policy=default)
        msg = parser.parsebytes(msg_bytes)
        self.assertEqual(msg.get_content_type(), 'text/plain')

    def test_missing_content_type(self):
        # Create a message with missing Content-Type header
        msg = """
        Hello, world!
        """
        msg_bytes = msg.encode('utf-8')
        parser = BytesParser(policy=default)
        msg = parser.parsebytes(msg_bytes)
        self.assertEqual(msg.get_content_type(), 'text/plain')

    def test_broken_boundary(self):
        # Create a message with broken boundary
        msg = """
        Content-Type: multipart/mixed; boundary="boundary"

        --boundary
        Hello, world!
        --boundary--
        """
        msg_bytes = msg.encode('utf-8')
        parser = BytesParser(policy=default)
        try:
            msg = parser.parsebytes(msg_bytes)
            self.fail("Expected MessageParseError")
        except MessageParseError:
            pass

    def test_non_ascii_subject(self):
        # Create a message with non-ASCII subject
        msg = """
        Subject: =?UTF-8?B?...?=
        """
        msg_bytes = msg.encode('utf-8')
        parser = BytesParser(policy=default)
        msg = parser.parsebytes(msg_bytes)
        self.assertEqual(msg.get('Subject'), decode_header(msg.get('Subject'))[0][0])

    def test_non_ascii_body(self):
        # Create a message with non-ASCII body
        msg = """
        Content-Type: text/plain; charset="utf-8"

        Hello, \u4e16\u754c world!
        """
        msg_bytes = msg.encode('utf-8')
        parser = BytesParser(policy=default)
        msg = parser.parsebytes(msg_bytes)
        self.assertEqual(msg.get_content_type(), 'text/plain')

    def test_non_ascii_sender_name(self):
        # Create a message with non-ASCII sender name
        msg = """
        From: =?UTF-8?B?...?=
        """
        msg_bytes = msg.encode('utf-8')
        parser = BytesParser(policy=default)
        msg = parser.parsebytes(msg_bytes)
        self.assertEqual(msg.get('From'), parseaddr(decode_header(msg.get('From'))[0][0]))

    def test_original_message_separator(self):
        # Create a message with Original Message separator
        msg = """
        Content-Type: text/plain; charset="utf-8"

        Hello, world!

        Original Message
        """
        msg_bytes = msg.encode('utf-8')
        parser = BytesParser(policy=default)
        msg = parser.parsebytes(msg_bytes)
        self.assertEqual(msg.get_content_type(), 'text/plain')

    def test_multiple_levels_of_quoting(self):
        # Create a message with multiple levels of quoting
        msg = """
        Content-Type: text/plain; charset="utf-8"

        > > Hello, world!
        """
        msg_bytes = msg.encode('utf-8')
        parser = BytesParser(policy=default)
        msg = parser.parsebytes(msg_bytes)
        self.assertEqual(msg.get_content_type(), 'text/plain')

if __name__ == '__main__':
    unittest.main()
```