import unittest
from scripts.intake_pipeline import process_question_body

class TestIntakePipelineTruncation(unittest.TestCase):

    def test_20k_body_not_truncated(self):
        # Cria um corpo de aproximadamente 20K caracteres usando o texto da issue
        base_text = "the misakanet dsh mcp intake sidebar fragment is alive "
        # Repete o texto até ultrapassar 20K, mas mantendo abaixo de 60K
        multiplier = 20000 // len(base_text) + 1
        body_20k = base_text * multiplier
        # Garante que temos pelo menos 20K caracteres
        self.assertGreaterEqual(len(body_20k), 20000)
        result = process_question_body(body_20k)
        # O resultado deve ser igual ao corpo de entrada, pois 20K < 60K
        self.assertEqual(result, body_20k)

    def test_truncation_at_60k(self):
        # Cria um corpo de 70K caracteres para testar truncamento
        body_70k = "a" * 70000
        result = process_question_body(body_70k)
        # Deve truncar em 60000 e adicionar uma mensagem de truncamento
        self.assertLess(len(result), 70000)
        self.assertLessEqual(len(result), 60000 + 100)  # Margem para a mensagem de truncamento
        self.assertIn("truncation notice", result.lower())  # Verifica se a mensagem está presente, case-insensitive

if __name__ == '__main__':
    unittest.main()
