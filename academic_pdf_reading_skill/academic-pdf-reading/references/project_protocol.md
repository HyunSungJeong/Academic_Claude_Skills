# Generating and maintaining a project-specific PDF protocol

Companion to `SKILL.md` (academic-pdf-reading v1.2.0). Read this when asked to
**create**, **update**, or **review** a project protocol, or when the staleness
check reports a mismatch and the user wants the protocol brought up to date.

## Contents
1. What a project protocol is for
2. What belongs in it, and what does not
3. Creating one
4. Verification standards
5. Hand-off and read-back
6. Updating one
7. Template

---

## 1. What a project protocol is for

The skill holds mechanisms; the project protocol holds **measured facts about
this project's files**: which container each one is, which failure modes its
text layer shows, its page offset, which glyph mappings have been verified on
the image, and which notation in this project is most at risk. It caches work
that would otherwise be repeated every session, and it carries a machine-
checkable inventory so that a changed file set is detected before stale facts
are used.

## 2. What belongs in it, and what does not

**Belongs:** the inventory (per file, one or more renditions, each with
SHA-256, size, container, pages and prose sketch; see `SKILL.md` §1.1); per-file
profile, split by rendition where it depends on the container; verified and provisional mappings with provenance; page offsets and
their basis; structural maps (where appendices, references, index start);
per-file grep conventions (equation-tag form, citation form); project-specific
traps; a changelog.

**Does not belong:**
- *General mechanisms* already in `SKILL.md` — refer to them ("mode B applies")
  instead of restating them. Restated rules drift.
- *Content knowledge* — errata in the papers, physics insights, derivations.
  Those go in the project's notes or chat summaries. The protocol is about
  *reading*, not about what the documents *say*.
- *Unverified claims presented as facts.* Every mapping is either
  `verified at p. N` or `provisional`.

## 3. Creating one

Work through the files in order; keep notes as you go.

1. **Inventory and profile.**
   ```bash
   python3 SKILL_DIR/scripts/triage.py profile /mnt/project/* --json /home/claude/profile.json
   python3 SKILL_DIR/scripts/triage.py inventory /mnt/project/* --root /mnt/project --out /home/claude/inv.json
   ```
   Exclude the protocol file itself if it already exists (the checker ignores
   `pdf_protocol_*.md` automatically).
2. **Container and channels** for each file, from the profile. Note anything
   surprising (a `.pdf` that is text; a ZIP that is not a paged archive).
3. **Failure modes.** For each file with a text channel, compare against the
   image: one displayed equation, one inline formula, one prose paragraph, and
   one figure caption. Record which of modes A, B, C are present, and where
   prose is or is not safe.
4. **Page offset.** From the profile's `folio` lines; confirm per §5 of
   `SKILL.md`. Record the basis ("e-locator folio, all 32 pages agree").
5. **Glyph mappings.** For every control byte, Private-Use character and
   substitution candidate the profile lists *and that matters for reading*
   (appears in math or in prose you will quote), establish the mapping per §7
   of `SKILL.md`. Test multi-valuedness. Record provenance. Rare glyphs may be
   left "unmapped" explicitly.
6. **Grep conventions.** Equation-tag form (ASCII, substituted, bracketed),
   citation form, column order, line endings.
7. **Structural map.** Section headers; where appendices, references and any
   index begin.
8. **Project-specific traps.** Ask: which notational features are
   load-bearing in *these* documents (overbars on indices, primes, calligraphic
   vs roman letters, Keldysh or contour labels, bold vectors), and does each
   file's text layer preserve them? Give one verified example per trap.
9. **Write the file** from the template (§7), named `pdf_protocol_<project>.md`,
   with the inventory JSON block embedded verbatim.
10. **Self-check** before handing it over:
    ```bash
    python3 SKILL_DIR/scripts/triage.py check /home/claude/pdf_protocol_<project>.md --root /mnt/project
    ```
    must report *up to date*.

## 4. Verification standards

- **Exhaustive where cheap.** Page offsets from a folio pattern: check every
  page (the script does). File hashes: every file.
- **Image-verified where it matters.** Every mapping used for math: at least
  one image check; at least three contexts of different kinds before calling
  a glyph single-valued.
- **Honest labels.** `verified at p. N (context)`, `provisional (context only)`,
  `unmapped`. Text-only files can only ever be `provisional` for math.
- **Record negative results** that save future effort ("manifest
  `has_visual_content` is true on all pages: useless"; "pdftoppm does not
  apply").

## 5. Hand-off and read-back

The protocol cannot be saved into project knowledge by Claude (project files
are read-only, and skills are global). So:

1. Write the file under `/mnt/user-data/outputs/` and present it.
2. The user uploads it to project knowledge, and adds to custom instructions a
   pointer such as:
   > PDF reading: follow the academic-pdf-reading skill. Project-specific
   > facts are in `pdf_protocol_<project>.md` in project knowledge; run its
   > staleness check on first use each session.
3. In the next session, the first use of the skill confirms the read-back: the
   file is present, its JSON block parses, and `triage.py check` passes. If the
   upload altered the file (run `triage.py profile` on it), say so.

## 6. Updating one

Triggered by a stale check, or by the user.

Source-file changes (`source +/-/~` in the check output) never trigger an
update on their own; the inventory may lag behind them. Fold them in at the
next update that happens for another reason: add inventory entries for new
sources, record any source–rendering pairing in the paired document's entry
("`X.tex` supersedes this file for content; keep the rendering for figures"),
and drop entries for removed sources and any pairing that names them.

- **Added file:** full creation procedure (§3, steps 2–8) for that file; add
  its inventory entry.
- **Removed file:** delete its entry and every fact that depends on it; note the
  removal in the changelog (future readers should know it once existed).
- **Changed file** (same name, different hash, reported `CHANGED`): treat as
  new. **Do not assume earlier mappings still hold**; the container itself may
  have changed. Regenerate its entry without `--add-rendition`, which retires
  its old renditions and every fact recorded for them.
- **Probable rendition swap** (`SWAP?`): first ask the user whether the file
  was edited or replaced. If it was, handle it as a changed file. If not:
  1. triage the mounted rendition (§3, steps 2–6) and record its
     container-dependent facts in a new rendition block of that file's entry
     (template, §7), leaving the existing rendition's block untouched;
  2. confirm the document-level facts (page offset, tag range, structure) on
     at least three spread pages of the new rendition and note that they hold
     for both;
  3. append it to the inventory with
     `triage.py inventory ... --merge OLD --add-rendition NAME...`, naming
     only the files the user confirmed.
  A rendition block whose facts were never measured is labelled
  "facts not yet recorded" rather than omitted, so a later session does not
  borrow another rendition's mappings.
- Regenerate the inventory block with `triage.py inventory`, using
  `--merge` with the current protocol so that recorded renditions are kept,
  bump the protocol's date, add a changelog line, re-run the self-check, hand
  off (§5).

## 7. Template

````markdown
# PDF reading protocol — <project>

Generated <date> with academic-pdf-reading v<version> (triage.py <version>).
General rules live in the skill; this file records facts about this project's
files only. Provenance labels: **verified at p. N** (checked on the page
image), **provisional** (context only), **unmapped**.

## Session start
Run on first use each session (and when files change):
`python3 SKILL_DIR/scripts/triage.py check /mnt/project/pdf_protocol_<project>.md`

## Inventory summary
| file (short) | container | channels | pages | printed-page offset (basis) | modes |
|---|---|---|---|---|---|

## Per-file facts
### <short name>
Document-level (hold for every rendition; confirmed on each):
- Printed-page offset (basis):
- Grep conventions: equation-tag range and form; citations.
- Structure:

#### Rendition: <container> (sha256 <first 12 hex>)
- Access:
- Text layer: modes present; what is safe; line endings; column order.
- Verified mappings:
- Provisional / unmapped:
- Geometry: image size or dpi; column gutter.

(Repeat the rendition block for each recorded rendition.)

## Project-specific traps
1. <trap>: <why it matters here>; example verified at <file> p. N.

## Changelog
- <date>: created.

## Inventory (machine-readable; used by `triage.py check`)
```json
{ "pdf_protocol_inventory": { ... } }
```
````
