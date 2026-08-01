import unittest

class TestSolution(unittest.TestCase):
    def test_print_ok(self):
        import io
        import sys
        capturedOutput = io.StringIO()
        sys.stdout = capturedOutput
        exec(open('solution.py').read())
        sys.stdout = sys.__stdout__
        self.assertEqual(capturedOutput.getvalue().strip(), 'ok')

if __name__ == '__main__':
    unittest.main()