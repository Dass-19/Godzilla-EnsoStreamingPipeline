---
id: 20260927152000
type: skill-spec
status: evergreen
name: "git-atomic-commit"
runtime: python / git diff
entrypoint: "sugerencia_de_commit"
inputs:
  - name: scope
    type: string
    description: "Área afectada (api, spark, producers, contracts, frontend, aos, tests)"
    required: false
outputs:
  format: "markdown | commit-suggestion"
created: 2026-09-27
updated: 2026-09-27
---

# Skill: Git Atomic Commit (Sugerencia de Commit)

> **REGLA ESTRICTA DE SEGURIDAD**: El agente de IA **NUNCA DEBE EJECUTAR `git commit` NI `git push` DIRECTAMENTE**.  
> Su función es ejecutar las pruebas automatizadas, analizar los diffs y **sugerir el comando y la descripción del commit** al usuario para su aprobación y ejecución manual.

---

## Cuándo Usar
Usar cuando una fase de un plan activo ha sido completada, todas las pruebas automáticas (`pytest -v`, `check_lint.py`) han pasado con éxito y se desea proponer al usuario un commit atómico y descriptivo.

## Protocolo Obligatorio del Agente
1. Ejecutar las pruebas unitarias y linters correspondientes.
2. Inspeccionar los cambios pendientes (`git status`, `git diff`).
3. Generar un bloque de código formateado con el comando `git commit` sugerido y una descripción clara en modo imperativo (Conventional Commits).
4. Presentar la sugerencia al usuario para que él realice el commit cuando lo considere oportuno.

---

## Formato del Mensaje Sugerido

```bash
git add <archivos_especificos>
git commit -m "<tipo>(<scope>): <descripción corta en imperativo>" -m "- <punto clave 1>" -m "- <punto clave 2>"
```

### Tipos Permitidos:
- `feat`: Nueva funcionalidad o capacidad.
- `fix`: Corrección de un bug o regresión.
- `refactor`: Reestructuración de código sin alterar comportamiento externo.
- `test`: Adición o mejora de pruebas unitarias/contratos.
- `docs`: Cambios en documentación o base de conocimiento.
- `chore`: Tareas de mantenimiento, dependencias o configuración.

---

## Ejemplos de Sugerencias para el Usuario

```bash
git commit -m "feat(api): agregar filtro por severidad en endpoint de alertas" -m "- Agrega parametro opcional severidad en GET /api/alertas" -m "- Valida esquema en schemas.py"
```

```bash
git commit -m "fix(spark): corregir ordenamiento temporal en bootstrap de EstadoFuentes" -m "- Lee particion mas reciente con kafka_timestamp descendente" -m "- Actualiza test_estado_fuentes.py"
```
