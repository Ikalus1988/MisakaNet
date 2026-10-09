import requests
import subprocess
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class DownloadManager:
    """
    Gerencia downloads de datasets com suporte a fallback de proxy para contornar 
    instabilidades em conexões diretas com GitHub e HuggingFace.
    """
    
    PROXIES = [
        "https://ghfast.top/",
        "https://gh-proxy.com/"
    ]
    
    TIMEOUT = 30  # Segundos para timeout de conexão inicial
    MAX_RETRIES = 2

    @staticmethod
    def _is_github_url(url: str) -> bool:
        return "github.com" in url

    @staticmethod
    def _has_trailing_dot(repo_name: str) -> bool:
        return repo_name.endswith('.')

    @classmethod
    def download_github_zip(cls, repo_owner: str, repo_name: str, dest_path: str) -> bool:
        """
        Tenta baixar o ZIP do repositório. Se o nome do repo terminar com '.',
        usa git clone via proxy para evitar 404 nos proxies de ZIP.
        """
        base_url = f"https://codeload.github.com/{repo_owner}/{repo_name}.zip"
        
        # Caso especial: Repositórios com ponto no final (ex: owner/repo.)
        # Proxies de ZIP costumam retornar 404 para esses casos.
        if cls._has_trailing_dot(repo_name):
            logger.warning(f"Repo '{repo_name}' ends with a dot. Using git clone fallback.")
            return cls._git_clone_via_proxy(repo_owner, repo_name, dest_path)

        # Tentativa de download direto
        if cls._attempt_download(base_url, dest_path):
            return True

        # Fallback para Proxies
        for proxy_prefix in cls.PROXIES:
            proxy_url = f"{proxy_prefix}{base_url}"
            logger.info(f"Attempting download via proxy: {proxy_url}")
            if cls._attempt_download(proxy_url, dest_path):
                return True
        
        return False

    @classmethod
    def _attempt_download(cls, url: str, dest_path: str) -> bool:
        try:
            with requests.get(url, stream=True, timeout=cls.TIMEOUT) as r:
                r.raise_for_status()
                with open(dest_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
            return True
        except Exception as e:
            logger.error(f"Download failed for {url}: {e}")
            return False

    @classmethod
    def _git_clone_via_proxy(cls, owner: str, repo_name: str, dest_dir: str) -> bool:
        """
        Usa git clone através de um proxy para repositórios problemáticos.
        """
        # Remove o ponto final para o clone padrão, mas o proxy precisa da URL completa
        clean_repo = repo_name.rstrip('.')
        git_url = f"https://github.com/{owner}/{clean_repo}"
        
        for proxy_prefix in cls.PROXIES:
            proxy_git_url = f"{proxy_prefix}{git_url}"
            logger.info(f"Attempting git clone via proxy: {proxy_git_url}")
            try:
                # Usando --depth 1 para ser rápido (shallow clone)
                cmd = ["git", "clone", "--depth", "1", proxy_git_url, dest_dir]
                subprocess.run(cmd, check=True, capture_output=True)
                return True
            except subprocess.CalledProcessError as e:
                logger.error(f"Git clone failed via {proxy_prefix}: {e.stderr.decode()}")
                continue
        return False

    @classmethod
    def download_raw_file(cls, url: str, dest_path: str) -> bool:
        """
        Download de arquivos raw (GitHub/HuggingFace) com fallback de proxy.
        """
        if cls._attempt_download(url, dest_path):
            return True

        for proxy_prefix in cls.PROXIES:
            proxy_url = f"{proxy_prefix}{url}"
            logger.info(f"Attempting raw download via proxy: {proxy_url}")
            if cls._attempt_download(proxy_url, dest_path):
                return True
        
        return False
