import os
import csv
import shutil
from typing import Callable, List, Dict, Any
from datetime import datetime

class DataSplitter:
    """
    Implementação do padrão de desmembramento de arquivos de origem para garantir
    a consistência entre consumidores com diferentes lógicas de chave de atribuição.
    """

    def __init__(self, source_dir: str, target_dir: str, key_extractor: Callable[[Dict[str, Any]], str]):
        """
        :param source_dir: Diretório com os arquivos brutos (ex: exportações multi-dia).
        :param target_dir: Diretório de destino onde os arquivos serão distribuídos por chave.
        :param key_extractor: Função que extrai a chave de atribuição de uma linha (ex: extrair data da coluna).
        """
        self.source_dir = source_dir
        self.target_dir = target_dir
        self.key_extractor = key_extractor

    def split_files(self):
        """Executa o processo de leitura, agrupamento e escrita de arquivos atômicos."""
        if not os.path.exists(self.target_dir):
            os.makedirs(self.target_dir)

        for filename in os.listdir(self.source_dir):
            file_path = os.path.join(self.source_dir, filename)
            if os.path.isfile(file_path):
                self._process_file(file_path, filename)

    def _process_file(self, file_path: str, original_filename: str):
        """Lê o arquivo original e agrupa linhas por sua chave de atribuição."""
        groups: Dict[str, List[Dict[str, Any]]] = {}
        header: List[str] = []

        # Fase 1: Leitura e Agrupamento
        with open(file_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames
            if not header:
                return

            for row in reader:
                key = self.key_extractor(row)
                if key not in groups:
                    groups[key] = []
                groups[key].append(row)

        # Fase 2: Escrita de arquivos atômicos (Um arquivo por chave)
        for key, rows in groups.items():
            # Sanitização do nome da pasta/arquivo baseada na chave
            safe_key = "".join([c for c in key if c.isalnum() or c in (' ', '.', '_', '-')]).strip()
            output_dir = os.path.join(self.target_dir, safe_key)
            
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            output_file = os.path.join(output_dir, f"{safe_key}_split.csv")
            
            with open(output_file, mode='w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=header)
                writer.writeheader()
                writer.writerows(rows)
            
            print(f"Generated: {output_file} with {len(rows)} rows (Key: {key})")

def example_usage():
    """
    Exemplo de como usar o splitter para resolver o problema da issue.
    """
    # Simulação da lógica do Consumidor A (extrai data de uma coluna específica)
    def consumer_a_key_logic(row: Dict[str, Any]) -> str:
        # Supondo que a coluna se chame 'timestamp' ou 'date'
        return row.get('date', 'unknown_date')

    splitter = DataSplitter(
        source_dir='raw_exports',
        target_dir='processed_intake',
        key_extractor=consumer_a_key_logic
    )
    splitter.split_files()

if __name__ == "__main__":
    example_usage()
