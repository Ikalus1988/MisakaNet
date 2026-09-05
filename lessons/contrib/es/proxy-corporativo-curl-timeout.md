---
title: 'Timeout de curl detrás de proxy corporativo: inspección SSL rompe validación de certificados'
domain: devops
tags:
  - proxy
  - curl
  - red-corporativa
  - ssl
  - tls
  - mitm
status: published
created: '2026-09-05'
source: translation-corporate-proxy-curl-timeout
evidence_level: E2
lang: es
---

# Timeout de curl detrás de proxy corporativo

## Problema

Las peticiones `curl` a APIs externas fallan con timeout detrás de un proxy corporativo con inspección SSL habilitada. Común en entornos empresariales donde todo el tráfico pasa por un proxy que realiza inspección TLS man-in-the-middle.

Síntomas:
- `curl: (60) SSL certificate problem: unable to get local issuer certificate`
- `curl: (35) OpenSSL SSL_connect: Connection reset by peer`
- Las peticiones se cuelgan30-60 segundos y luego fallan

## Causa raíz

El proxy corporativo realiza inspección SSL man-in-the-middle:
1. Intercepta el handshake TLS con su propio certificado CA
2. Re-firma certificados del servidor con la CA corporativa
3. curl valida contra el almacén CA del sistema que no incluye la CA corporativa

## Solución

**Opción 1: Saltar verificación de certificado (rápido, menos seguro)**
```bash
curl --proxy-insecure https://api.example.com
# O configurar permanentemente
export CURL_INSECURE=1
```

**Opción 2: Agregar CA corporativa al almacén de confianza (recomendado)**
```bash
# Encontrar CA corporativa (preguntar a IT o revisar navegador)
cp corporate-ca.crt /etc/ssl/certs/
# O establecer por petición
curl --cacert /path/to/corporate-ca.crt https://api.example.com
# O configurar permanentemente
export CURL_CA_BUNDLE=/path/to/corporate-ca.crt
```

**Opción 3: Usar configuración de proxy del sistema**
```bash
curl --proxy http://proxy.corp:8080 https://api.example.com
# O configurar permanentemente
export http_proxy=http://proxy.corp:8080
export https_proxy=http://proxy.corp:8080
```

## Verificación

```bash
curl -sS -o /dev/null -w '%{http_code}' https://api.example.com
# Debería retornar 200
```

## Referencias

- [Documentación curl: SSL CERTS](https://curl.se/docs/sslcerts.html)
- [Stack Overflow: curl detrás de proxy corporativo](https://stackoverflow.com/questions/29822686)
