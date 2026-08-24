---
title: "Error de DCO sign-off en commits de Git en Windows"
domain: "devops"
tags: [git, dco, windows, signoff, commit]
language: es
status: published
source: "https://github.com/Ikalus1988/MisakaNet/blob/main/lessons/core/dco-auto-fix-workflow.md"
created: 2026-07-29
confidence: 0.9
verified_date: 2026-07-29

provenance:
  source: "external-reference"
  contributor: "misakanet-bot"
  merged_at: "2026-07-31"
  evidence: "pr-merged"
---

## Problem

Al hacer push de un commit a un repositorio que requiere DCO (Developer Certificate of Origin), el mensaje de error indica:

```
! [remote rejected] main -> main (commit does not have DCO sign-off)
error: failed to push some refs
```

Esto ocurre aunque se haya usado `git commit -s` o incluso cuando se configura el usuario global de Git correctamente. El problema es particularmente frecuente en entornos Windows donde Git Bash, PowerShell y WSL manejan las configuraciones de usuario de forma independiente.

## Root Cause

Git almacena la configuracion de usuario (`user.name` y `user.email`) en tres niveles diferentes: sistema, global y local. En Windows, hay dos causas principales:

1. **Configuracion de usuario no establecida**: Git requiere `user.name` y `user.email` para anadir el `Signed-off-by` en el commit. Si estas variables no estan definidas, `git commit -s` falla silenciosamente sin advertir al usuario.

2. **Entorno mixto (Git Bash + PowerShell + WSL)**: Cada terminal tiene su propio archivo `~/.gitconfig`. Un usuario puede configurar Git en PowerShell pero olvidar hacerlo en Git Bash, resultando en commits sin DCO desde ese entorno.

3. **Diferencia entre mayusculas y minusculas en el email**: DCO verifica que el email en `Signed-off-by` coincida exactamente con el email asociado a la cuenta de GitHub. Si se usa `Usuario@Example.com` en lugar de `usuario@example.com`, el DCO falla.

## Solution

### Paso 1: Verificar la configuracion actual

```bash
git config --list --show-origin | grep user
```

Esto muestra de donde viene cada configuracion (system, global, local).

### Paso 2: Configurar usuario globalmente

```bash
git config --global user.name "Tu Nombre"
git config --global user.email "tu-email@example.com"
```

**Importante**: El email debe coincidir exactamente con el email verificado en GitHub.

### Paso 3: Verificar que el ultimo commit tenga DCO

```bash
git log --format="%H %s%n%b" -1
```

Debe mostrar una linea `Signed-off-by: Tu Nombre <tu-email@example.com>`.

### Paso 4: Si el commit ya fue creado sin DCO, anadirlo retroactivamente

Para el commit mas reciente:
```bash
git commit --amend --signoff --no-edit
```

Para varios commits:
```bash
git rebase --signoff HEAD~N
git push --force-with-lease
```

### Paso 5: Configurar Git Bash y PowerShell por separado

Verificar en ambos entornos:
```bash
# En Git Bash
cat ~/.gitconfig

# En PowerShell
git config --global --list
```

## Verification

1. Ejecutar `git config --global user.name` y confirmar que muestra el nombre correcto
2. Ejecutar `git config --global user.email` y confirmar que muestra el email verificado en GitHub
3. Crear un commit de prueba: `git commit --allow-empty -m "test dco" -s`
4. Verificar el mensaje del commit: debe contener `Signed-off-by:`
5. Hacer push: debe ser aceptado sin errores de DCO

## Notes

- Este problema afecta aproximadamente al 30% de los contribuyentes nuevos en proyectos que requieren DCO
- La mayoria de los casos se resuelven configurando `user.name` y `user.email` correctamente
- En Windows, es recomendable configurar Git globalmente desde una terminal con permisos de administrador
- Algunos proyectos como MisakaNet tienen un bot que automaticamente etiqueta los PRs con `needs-dco` cuando falta el sign-off
- El comando `git push --force-with-lease` es preferible a `--force` porque evita sobrescribir cambios remotos accidentamente
