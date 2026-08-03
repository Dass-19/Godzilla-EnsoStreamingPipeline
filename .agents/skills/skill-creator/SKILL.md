---
name: skill-creator
description: 'Use this skill when creating, refactoring, evaluating, or auditing agent skills. Guides the agent through standard skill directory structure, YAML frontmatter conventions, instruction formatting, trigger phrases, scope boundary definition, and validation checklists. Trigger phrases: "create a skill", "build a skill", "add a new skill", "skill creator", "refactor skill", "skill guidelines".'
---

# Skill Creator & Standard Guidelines

## Overview
This skill provides a comprehensive meta-framework for creating, structuring, and maintaining agent skills within repositories. A **Skill** is a modular package of domain-specific instructions, architectural context, code standards, and tools designed to guide AI agents when working on specific components or subsystems.

---

## 1. Skill Anatomy & Directory Layout

In this project, every skill lives inside its own subdirectory under `.agents/skills/` (workspace-level,
checked into git alongside the code it documents — that's the only location in use here).

```
.agents/skills/<skill-name>/
├── SKILL.md                 # MANDATORY: Instructions with YAML frontmatter (< 500 lines)
├── scripts/                 # OPTIONAL: Helper scripts or code generators
├── references/              # OPTIONAL: Detailed documentation, API schemas, design specs
├── resources/               # OPTIONAL: Templates, sample data, asset files
└── examples/                # OPTIONAL: Reference code patterns & usage examples
```

---

## 2. YAML Frontmatter Specification

The `SKILL.md` file MUST start with a valid YAML frontmatter block containing `name` and `description`.

```yaml
---
name: skill-name-kebab-case
description: 'Use this skill when [specific context/trigger condition]. Includes guidance for [key capabilities/components]. Trigger phrases: "phrase 1", "phrase 2", "phrase 3".'
---
```

### Frontmatter Rules:
1. **`name`**: Unique, lower-case, kebab-case string (e.g., `backend-producers`, `testing`). Must match folder name.
2. **`description`**: Single line string summarizing **when** the skill should be invoked and **what** it addresses. Always include explicit trigger phrases.
3. **Trigger Phrases**: Use high-intent phrases that match likely user requests or agent task contexts.

---

## 3. SKILL.md Writing Standards

### Key Writing Principles:
- **Declarative & Actionable**: State rules clearly and direct the agent on exact actions to take or avoid.
- **Concise & Scoped**: Keep `SKILL.md` under 500 lines. Place extensive reference documents in `references/`.
- **Repo-relative file links, never absolute**: reference files with a relative markdown link from the
  skill's own directory (`[app.py](../../../backend/api/app.py)`), the same convention this project's own
  `CLAUDE.md` uses. **Never use an absolute `file:///C:/Users/<name>/...` URI** — it's tied to one
  machine's checkout path and silently breaks (dead link, no error) the moment the repo is cloned
  elsewhere or opened by another contributor. This happened for real in this repo: every skill under
  `.agents/skills/` shipped with `file:///c:/Users/H%20P/Desktop/...` links from a different machine, all
  dead on the current one.
- **Verify every factual claim against the code before writing it, don't describe from memory or
  intent**: read the actual file, grep for the function/constant/pattern named, and quote what's really
  there. A skill is loaded into an agent's context as ground truth — a wrong claim (a made-up config
  format, a category name that doesn't match the code, a "the API imports X" that isn't true) doesn't
  just fail to help, it actively steers the agent into reintroducing the exact bug the skill claims to
  guard against. If a described pattern is aspirational (a recommendation for how new code *should* look)
  rather than something already in the codebase, say so explicitly — don't present it as existing fact.
- **Code Block Examples**: Provide exact code snippets illustrating correct usage patterns vs anti-patterns.

### Recommended Structure for SKILL.md:
1. **Overview & Scope**: Purpose of the skill and target codebase components.
2. **Architecture & Design Principles**: Core patterns, data flows, and structural rules.
3. **Implementation Standards & Code Snippets**: Concrete coding patterns, imports, type hints, error handling.
4. **Key Files & Entry Points**: Explicit list of files modified or consumed by this subsystem.
5. **Validation & Verification Workflow**: Commands to run and assertions to verify.

---

## 4. Decision Matrix: Skill vs Rule vs Artifact vs Code

| Type | Best For | Location | Example |
|---|---|---|---|
| **Skill** | Subsystem/component workflows, domain guides, testing strategies | `.agents/skills/<skill>/SKILL.md` | `backend-producers`, `testing` |
| **Rule** | Workspace-wide or global constraints, non-negotiable policies | `AGENTS.md` | "Never edit .ipynb files directly" |
| **Artifact** | User-facing plans, research reports, walkthroughs | `<appDataDir>/brain/<conv-id>/` | `implementation_plan.md` |
| **Script/Code** | Automated executable utilities or tests | `<skill>/scripts/` or `tests/` | `run_producers.py` |

---

## 5. Step-by-Step Skill Creation Workflow

1. **Identify the Component Scope**:
   - Determine which directory, subsystem, or technology layer the skill covers (e.g., PySpark pipeline, Kafka producers, API, frontend).
2. **Inspect Existing Code & Patterns**:
   - Read the primary entry points and contracts to capture realistic file paths, variable names, and design patterns.
3. **Scaffold Directory**:
   - Create `.agents/skills/<skill-name>/SKILL.md`.
4. **Draft YAML Frontmatter**:
   - Ensure `name` matches the directory and `description` contains clear trigger conditions.
5. **Formulate Guidelines**:
   - Write structured sections for architecture, standards, file locations, error handling, and testing.
6. **Validate & Test**:
   - Verify YAML frontmatter syntax, inspect Markdown formatting, and test trigger responsiveness.

---

## 6. Verification Checklist

Before finalizing any skill, verify:
- [ ] Directory name matches `name` in YAML frontmatter.
- [ ] YAML frontmatter is enclosed between `---` lines with valid syntax.
- [ ] Description includes clear trigger phrases.
- [ ] Every file path is a **repo-relative** markdown link (never `file:///C:/Users/...` or any other
      machine-specific absolute path) — click-test a couple from the skill's own directory.
- [ ] Every concrete claim (function name, constant, category value, "X imports Y") was checked against
      the current code, not written from memory of an earlier version or from what the design intended.
- [ ] `SKILL.md` is concise (<500 lines) and directly actionable.
