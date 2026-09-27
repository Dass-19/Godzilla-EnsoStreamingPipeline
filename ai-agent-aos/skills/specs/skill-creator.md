---
id: 20260927152007
type: skill-spec
status: evergreen
name: "skill-creator"
runtime: markdown / aos
entrypoint: "ai-agent-aos/skills/specs/"
inputs:
  - name: skill_name
    type: string
    description: "Nombre de la nueva skill en formato kebab-case"
    required: true
outputs:
  format: "markdown spec / bin executable"
created: 2026-09-27
updated: 2026-09-27
---

# Skill: Skill Creator (Meta-Skill)

> **Propósito**: Guiar la creación, estandarización y auditoría de nuevas skills y scripts dentro del sistema AI-AGENT-AOS.

---

## 1. Estructura Estándar de una Skill

Toda nueva capacidad debe crearse bajo [`ai-agent-aos/skills/`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/ai-agent-aos/skills/) dividida en dos componentes:

1. **Especificación Declarativa (`specs/[nombre-skill].md`)**:
   - Frontmatter YAML canónico con `id`, `type: skill-spec`, `status: evergreen`, `name`, `runtime`, `entrypoint`, `inputs` y `outputs`.
   - Propósito y casos de uso precisos.
   - Comandos de ejecución deterministas.
   - Manejo de códigos de salida (exit codes).
2. **Ejecutable Auxiliar (`bin/[script.py]`)**:
   - Script ejecutable cross-platform con argparse / sys.argv y retorno de exit codes estándar (0 = éxito, >0 = error).

---

## 2. Checklist de Validación
- [ ] La especificación incluye frontmatter YAML válido.
- [ ] Si incluye script en `bin/`, es compatible con Windows y Linux.
- [ ] La skill está registrada en [`ai-agent-aos/00-INDEX.md`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/ai-agent-aos/00-INDEX.md).
