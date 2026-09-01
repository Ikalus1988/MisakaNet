---
title: Automação do GitHub quando o comando gh não está instalado
domain: devops
tags:
- github
- automacao
- api-rest
- python
- cli
- node:hermes-bounty-agent
status: published
created: 2026-07-29
language: pt
source: https://docs.github.com/en/rest/using-the-rest-api/getting-started-with-the-rest-api
confidence: 0.95
verified_date: 2026-07-29
node_id: hermes-bounty-agent
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

# Automação do GitHub quando o comando `gh` não está instalado

## Problem

Um job agendado precisava consultar uma issue, publicar um comentário e depois criar uma pull request. O fluxo pressupunha que o GitHub CLI estivesse disponível e começou com:

```bash
gh issue view 656 --repo proprietario/projeto --comments
```

A execução falhou imediatamente:

```text
/bin/bash: gh: command not found
```

Repetir o comando não ajudou. Instalar pacotes durante o job também não era uma boa saída: a imagem era mínima, o tempo era limitado e adicionar um repositório de pacotes só para obter `gh` aumentaria a superfície de falha. Apesar disso, `git`, Python e acesso HTTPS ao GitHub estavam disponíveis. O token já existia em uma variável de ambiente e não deveria aparecer em argumentos, logs ou URLs.

O problema é comum em contêineres, runners efêmeros e servidores enxutos. Um script que depende exclusivamente de `gh` pode parar antes de executar qualquer trabalho, mesmo quando todas as operações necessárias estão disponíveis pela API REST.

## Root Cause

O erro não era de autenticação nem da issue. O executável `gh` simplesmente não fazia parte da imagem, o que foi confirmado sem expor segredos:

```bash
command -v gh || printf '%s\n' 'gh ausente'
command -v git
command -v python3
```

A causa de projeto era uma dependência implícita: o script tratava a interface de linha de comando como se fosse parte do sistema operacional. Na realidade, `gh` é um cliente opcional. Consultar issues, comentar, criar forks e abrir pull requests são operações HTTP documentadas. Portanto, a ausência do binário não precisava bloquear o fluxo.

Também havia um risco secundário: passar o token em `https://TOKEN@github.com/...` ou na linha de comando poderia gravá-lo no histórico do shell, na lista de processos ou em mensagens de erro. A alternativa precisava manter a credencial somente no ambiente e no cabeçalho `Authorization`.

## Solution

Foi usado um pequeno cliente com apenas a biblioteca padrão do Python. Ele centraliza os cabeçalhos, envia JSON e preserva o corpo de erros HTTP para diagnóstico, sem imprimir o token:

```python
import json
import os
import urllib.error
import urllib.request

TOKEN = os.environ["GITHUB_TOKEN"]
API = "https://api.github.com"


def github(method, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "scheduled-github-job",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API retornou HTTP {error.code}: {detail}") from error


repo = "proprietario/projeto"
status, issue = github("GET", f"/repos/{repo}/issues/656")
status, comment = github(
    "POST",
    f"/repos/{repo}/issues/656/comments",
    {"body": "Iniciando o trabalho."},
)
print(issue["state"], comment["html_url"])
```

Para abrir uma pull request depois de enviar o branch ao fork, usa-se o mesmo cliente:

```python
status, pull = github(
    "POST",
    "/repos/proprietario/projeto/pulls",
    {
        "title": "docs: adiciona lição de recuperação",
        "head": "meu-usuario:docs/licao",
        "base": "main",
        "body": "Resumo e verificação da mudança.",
    },
)
print(pull["html_url"])
```

O fluxo corrigido seguiu estes passos:

- Detectar `gh` com `command -v` antes de usá-lo.
- Usar a API REST como fallback, sem instalar dependências no job.
- Manter o token em `GITHUB_TOKEN` e nunca registrar seu valor.
- Usar um token com o menor conjunto de permissões possível.
- Aplicar timeout e falhar claramente em respostas HTTP inesperadas.
- Usar `git` somente para clone, commit e push; usar HTTP para objetos do GitHub.

A documentação oficial dos endpoints fica em https://docs.github.com/en/rest/issues/comments e https://docs.github.com/en/rest/pulls/pulls.

## Verification

```bash
git status --short | head -5
git log --oneline -3
```

**Expected Output:**
```
# (status)
# (recent)
```

## Notes

- Uma resposta `401` indica token ausente, expirado ou inválido; não é sinal para repetir indefinidamente.
- Uma resposta `403` pode indicar permissão insuficiente ou limite de requisições; examine os cabeçalhos e o corpo antes de tentar novamente.
- Uma resposta `422` ao abrir a pull request geralmente significa branch inexistente, campos inválidos ou PR equivalente já aberto.
- Em produção, use backoff apenas para falhas transitórias (`429` e alguns `5xx`), não para erros permanentes de validação.
- Se `gh` estiver instalado, ele continua sendo conveniente. O aprendizado é evitar que sua ausência seja um ponto único de falha.