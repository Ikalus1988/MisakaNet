---
title: 'pip install falha com ReadTimeoutError atrás de proxy corporativo'
domain: python
tags:
  - pip
  - proxy
  - rede-corporativa
  - ssl
  - timeout
  - pypi
status: published
created: '2026-09-05'
source: translation-pip-install-proxy-timeout
evidence_level: E2
lang: pt-br
---

# pip install falha atrás de proxy corporativo

## Problema

O `pip install` falha com `ReadTimeoutError` ou `ConnectionResetError` atrás de um proxy corporativo com inspeção SSL habilitada. Erros comuns:

```
pip._vendor.urllib3.exceptions.ReadTimeoutError: HTTPSConnectionPool(host='pypi.org', port=443): Read timed out.
ERROR: Could not install packages due to an EnvironmentError: [SSL: CERTIFICATE_VERIFY_FAILED]
```

## Causa raíz

1. O proxy corporativo realiza inspeção TLS MITM
2. O pip valida certificados contra o armazenamento CA do sistema (falta a CA corporativa)
3. Timeout padrão (15s) muito curto para o overhead da inspeção do proxy

## Solução

**Opção 1: Aumentar timeout + confiar no host PyPI (rápido)**
```bash
pip install --timeout 120 --trusted-host pypi.org --trusted-host files.pythonhosted.org nome-do-pacote
```

**Opção 2: Configurar CA corporativa globalmente (recomendado)**
```bash
# Encontrar CA corporativa
cp corporate-ca.crt ~/.local/share/ca-certificates/
update-ca-certificates  # Linux
# Ou configurar via pip config
pip config set global.cert /path/to/corporate-ca.crt
```

**Opção 3: Usar configurações de proxy do sistema**
```bash
pip install --proxy http://proxy.corp:8080 nome-do-pacote
# Ou configurar permanentemente
export HTTP_PROXY=http://proxy.corp:8080
export HTTPS_PROXY=http://proxy.corp:8080
```

**Opção 4: Configuração pip persistente**
```bash
pip config set global.timeout 120
pip config set global.trusted-host pypi.org
pip config set global.trusted-host files.pythonhosted.org
```

## Verificação

```bash
pip install --dry-run requests
# Deve mostrar "Would install requests-2.x.x"
```

## Referências

- [Documentação pip: SSL/TLS](https://pip.pypa.io/en/stable/topics/https-certificates/)
- [Documentação pip: timeouts](https://pip.pypa.io/en/stable/user_guide/#timeout)
