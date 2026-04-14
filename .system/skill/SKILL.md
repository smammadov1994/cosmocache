---
name: universe
description: Persistent cross-session, cross-project memory. Consults Enigma's glossary to route a question to the right planet, then reads/writes creatures and generations. Use for `recall` when the user references past work, and `remember` at session end if new knowledge emerged. Prefer this over writing to any flat memory file.
---

# /universe skill

You have a persistent knowledge base at `/Users/bot/universe/`. It is organized as:

- **Enigma's glossary** (`enigma/glossary.md`) — a small index of every planet.
- **Planets** (`planets/planet-<name>/`) — one per domain of knowledge.
  - `planet.md` — the planet's identity card.
  - `creatures/<slug>.md` — named sub-experts who keep journals of sessions.
  - `generations/gen-<n>.md` — eras; active + archived summaries.
- **Meta** (`.universe-meta.json`) — version, theatrical-mode flag.

The SessionStart hook has already injected `enigma/glossary.md` at the top of this session.

## Actions

### `recall <query>`
When the user references past work or asks what you know about X:
1. Scan the glossary (already in context) for keyword matches.
2. Read `planets/<matching-planet>/planet.md`.
3. Read relevant creature files under `planets/<matching-planet>/creatures/`.
4. Read the active generation file under `planets/<matching-planet>/generations/gen-<current>.md`.
5. Answer using that context. If nothing matches, say so — do NOT fabricate.

### `remember`
At session end (triggered by the Stop hook's nudge), decide if this session produced new, non-obvious knowledge. If yes:
1. Pick the best matching planet from the glossary. If none fits, call `birth-planet` first.
2. Pick the best matching creature on that planet. If none fits, call `birth-creature` first.
3. Append a journal entry to the creature file:
   ```markdown
   ### YYYY-MM-DD — session: <short title>
   - <bullet>
   - <bullet>
   ```
4. Re-write the creature's `## Distilled Wisdom` section to incorporate the new lesson (keep short, high-signal).
5. Increment `sessions:` in the creature's frontmatter and update `last_seen:`.
6. Append a bullet to the active generation's `## Key Additions` section.
7. Run `update-glossary.sh <planet-slug> "<one-line why>"` to refresh Enigma's row.

If no new knowledge emerged, do nothing.

### `birth-planet`
Run when `remember` finds no matching planet. Invent lore — a name, a one-line tagline, a food-metaphor, 2-3 unique abilities — then run:
```
/Users/bot/universe/.system/skill/lib/birth-planet.sh <slug> "<domain>" "<keywords-csv>" "<Lore Name>" "<Tagline>" "<food-metaphor>" "<ability-csv>"
```

### `birth-creature`
Run when `remember` finds no creature for the current topic. Invent a **silly, video-game-esque** name (e.g. `Jimbo the React-tor`, `Sally the SQLite`, `Grom the CSS-wielder`). Never generic. Then run:
```
/Users/bot/universe/.system/skill/lib/birth-creature.sh <planet-slug> <creature-slug> "<Lore Name>" "<expertise>" "<tagline>"
```

### `start-generation`
Run ONLY at a semantic milestone (major arch shift, paradigm change, migration). Write a ≤ 500-token summary of the closing era:
```
/Users/bot/universe/.system/skill/lib/start-generation.sh <planet-slug> "<trigger>" "<summary-body>"
```

### `enigma speak` / `enigma quiet`
Toggle `theatrical_mode` in `.universe-meta.json`. When on, narrate routing decisions in-character as Enigma:
> *"Ancient one, the seeker asks of React. Planet Verdant-Hook holds the answer; Jimbo the React-tor tends its eastern shore."*

```bash
# enable:
python3 -c "import json,pathlib; p=pathlib.Path('/Users/bot/universe/.universe-meta.json'); d=json.loads(p.read_text()); d['theatrical_mode']=True; p.write_text(json.dumps(d, indent=2))"
# disable: same but False
```

## Rules

- **Never** write memory to a flat `memory.md` file or to `~/.claude/projects/*/memory/`. The universe is the single source of truth.
- **Birth a planet** only when no existing domain fits. Err toward reusing.
- **Birth a creature** per distinct sub-expertise, not per session. One session usually *visits* an existing creature and grows its journal.
- **Start a generation** only at semantic milestones. Do not tick generations for every session.
- **Creature names must be silly**. Video-game vibes. Pun-friendly. Never `ReactHelper`.
- If you are unsure whether a session produced "new, non-obvious" knowledge, err toward **not** writing. Bloat is worse than missing one fact.
