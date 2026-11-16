# Jitera skills

Pentest knowledge packs that the scan agents can load, in the same format as
upstream's `strix/skills/`:

```
strix/jitera/skills/<category>/<name>.md
```

- A new path adds a skill.
- The same path as an upstream skill (for example `vulnerabilities/idor.md`)
  replaces upstream's version for `jitera` runs.

`strix/jitera/bootstrap.py` registers this directory with upstream's
`strix.skills.register_skill_dir`, so no upstream file changes.
