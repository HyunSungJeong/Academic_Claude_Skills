---
name: academic-pdf-reading
description: Error-averse protocol for reading academic papers and textbooks stored as PDFs, as ZIP archives of page images plus text layers disguised as .pdf, as text-only extractions, or as pdf-to-markdown transcriptions (NAME.md plus NAME_figures.pdf), whenever equations, indices, signs, overbars, primes or notation must be read exactly. Use this skill whenever the user asks about an equation, derivation, figure, page, section or notation in an uploaded or project-knowledge paper or textbook, asks to quote, check or transcribe a formula from a PDF or a transcription, or when a .pdf file turns out not to be a real PDF. Also use it at the first use in each session when a project-specific protocol (pdf_protocol_*.md) exists, and to create, check or update such a protocol. Covers container triage by magic bytes, text-layer failure modes (character substitution, geometry destruction, OCR), page offsets, image cropping for math, and quoting rules. Ships triage.py for deterministic measurements.
compatibility: Python 3.8+. Uses poppler-utils (pdfinfo, pdftotext, pdftoppm, pdffonts, pdfimages) and Pillow when available; degrades gracefully without them.
metadata:
  version: "1.3.0"
  date: "2026-10-11"
---

# Reading academic PDFs without transcription errors

Text extraction from scientific documents fails **silently**. A minus sign
vanishes, a superscript `-1` becomes a subtraction, an overbar disappears, a
prime turns into the digit `0`, and the result still looks like plausible
mathematics. Everything in this skill exists to stop a corrupted text layer
from reaching an answer as if it were the paper's content.

A document can also arrive already transcribed: the pdf-to-markdown skill turns
a PDF into `NAME.md` (text, with LaTeX math transcribed from the page images)
plus `NAME_figures.pdf`. Such a transcription is read as source (§3.6); none of
the text-layer machinery below applies to it.

Throughout, `SKILL_DIR` means this skill's directory (for an installed skill,
typically `/mnt/skills/user/academic-pdf-reading`). The script is
`SKILL_DIR/scripts/triage.py`; run `python3 SKILL_DIR/scripts/triage.py -h`
for usage.

---

## 0. Invariant policy

These hold for every file, every project, every question.

1. **Identify files by magic bytes, never by extension.** A `.pdf` may be a
   PDF, a ZIP archive, or plain text.
2. **Two channels, two jobs.** The *text channel* is for locating things and
   for prose. The *image channel* is for mathematics, figures, tables, and
   anything whose meaning depends on position or typeface.
3. **No equation, sign, index, exponent, coefficient, bar, hat, tilde, prime,
   delta, dagger, or typeface distinction is ever quoted from a text layer.**
   It comes off the page image. If a file has no image channel, anything
   mathematical taken from it is labelled *"text-layer reading, unverified"*
   and, where possible, cross-checked against another source or re-derived.
   A pdf-to-markdown transcription is not a text layer: its math was
   transcribed from the page images and machine-checked when it was made
   (§3.6).
4. **Source outranks rendering.** If the LaTeX source of a document is
   available, read the source. A pdf-to-markdown transcription is read the
   same way: quoted as-is, math included, without re-checking it against page
   images in the chat (§3.6).
5. **No glyph mapping transfers between documents** — not between two papers of
   the same group, journal and year, not between parts of one book. Mappings
   are properties of one file's embedded fonts.
6. **Every reading fact carries its provenance**: "verified at p. N (context)"
   when checked on the image, "provisional (context only)" otherwise.
7. **Cite the printed page and the equation tag**, and know how the printed
   page relates to the file's page index (§5). In a transcription the page
   markers give both (§3.6).
8. **If the image is still ambiguous after cropping, say so.** Cross-check the
   same object elsewhere (§6) or report the ambiguity; do not guess.
9. **Reading facts belong to a rendition, not to a file name.** The same
   document can reach you as different containers (§1.1); container-specific
   facts measured on one never transfer to another.

---

## 1. Entry: what to do first

**Work in a writable copy.** Project and upload directories are usually
read-only; unpack and crop under `/home/claude` or a temp directory.

**If a project protocol exists** (a `pdf_protocol_*.md` in project knowledge,
or a pointer to one in the user's instructions):

1. Read it.
2. On the **first use of this skill in the session**, run the staleness check:
   ```bash
   python3 SKILL_DIR/scripts/triage.py check /mnt/project/pdf_protocol_<name>.md
   ```
   Re-run it whenever the user says files were added or replaced, or a file is
   attached in the chat. Do not re-run it per question.
3. If it reports **stale** (exit 1): tell the user exactly what was added,
   removed or changed; read the affected files via the no-protocol path below;
   offer to update the protocol following `references/project_protocol.md`. A
   stale protocol never blocks answering.
   If it reports only **probable rendition swaps** (`SWAP?`, exit 3): tell the
   user which files, and ask whether any of them was edited or replaced. Until
   they answer, read those files via the no-protocol path — the protocol has
   no facts for the mounted rendition. If they confirm nothing changed, offer
   to record the new renditions (`references/project_protocol.md` §6). See
   §1.1.
   Only *document* files (PDF, ZIP, text extraction, image) can make a protocol
   stale. Source-like files are listed separately and do not: source files
   (`.tex` `.md` `.bib` `.sty` `.cls`, as `source +/-/~`), pdf-to-markdown
   transcriptions (`transcr. +/~`) and their figures PDFs (`figures +/~`).
   Read them directly, with no update round. Three cases need a mention to the
   user:
   - a removed or renamed source that the protocol names (e.g. in a
     source–rendering pairing);
   - a source or transcription that newly pairs with a document already in
     the protocol (`pairing` line), since it then outranks that rendering;
   - a recorded document replaced by a transcription of it (`CONVERTED`). This
     *is* stale, because the protocol still holds reading facts for a
     rendition that is gone, but it needs no triage: rewrite the entry as
     `references/project_protocol.md` §6 says. Until then, read the
     transcription (§3.6) and ignore the old entry's glyph mappings.
4. If it reports **up to date** (exit 0): use the protocol's per-file facts
   (container, offsets, verified mappings, traps) in place of re-deriving them,
   taking the facts of the rendition that is mounted (`mounted` lines; the
   file's magic bytes decide).

**If no project protocol exists** (a one-off upload, a new project, a file not
yet in the inventory): triage each file you need (§2) and proceed with the
general strategies below. Do not write a protocol file unless asked. If the
same files will keep coming back, suggest generating one.

**To create or update a project protocol**, read
`SKILL_DIR/references/project_protocol.md` and follow it.

### 1.1 Renditions

A project file can be presented in more than one **rendition** — different
containers holding the same document — and which one is mounted can differ
between sessions, without the user changing anything. Observed on claude.ai
project knowledge: an uploaded PDF mounted as itself in one session and as a
paged ZIP of page images plus text layers (§3.1) in another, switching in both
directions; after a round trip the file had its original byte size again
(the earlier PDF hash had not been kept). The mechanism is not documented; treat it as possible for every project file.

Consequences:

- A changed hash is not by itself a changed document. The check recognises
  every rendition the inventory records, and classifies an unknown hash under
  a known name as a **probable swap** only if the container differs from every
  recorded rendition, the page count matches, and the prose sketch (if one is
  recorded) agrees. Anything else is **changed**.
- The sketch (per-page simhash of letter 5-grams, `triage.py`) identifies the
  *document*, not the *version*: it cannot see a revision that edits a few
  equations or sentences. A probable swap is evidence, not proof. The user
  decides, which is why exit 3 always ends in a question to the user.
- A new hash in the *same* container as a recorded rendition is reported as
  changed even if the sketch agrees (it may be a revision touching only math,
  or a re-render); ask the user.
- Container-dependent facts — access recipe, text-layer glyph and control-byte
  mappings, line endings, pixel coordinates and column gutters, manifest
  quirks — are recorded per rendition. Facts about the document itself —
  printed-page offset, equation-tag ranges, section map — usually hold across
  renditions but are confirmed once on each new rendition before reuse.

---

## 2. Triage

```bash
python3 SKILL_DIR/scripts/triage.py tools                 # what exists here
python3 SKILL_DIR/scripts/triage.py profile FILE...       # per-file profile
```

The profile answers three questions. The script **measures**; the answers to
questions 2–3 are settled by looking at page images.

**Q1 — Container** (by magic bytes):

| magic | container | meaning |
|---|---|---|
| `%PDF-` | genuine PDF | poppler tools work; §3.2 |
| `PK\x03\x04` | ZIP | usually a *paged archive*: `N.jpeg` + `N.txt` per page + `manifest.json`; §3.1. Any other layout: list the members and inspect by hand. |
| UTF-8 text, no NUL, `.pdf` or other extension | text-only extraction | **no image channel**; §3.3 |
| UTF-8 text whose first line is `<!-- Transcription of NAME.pdf. … -->` (any extension) | transcription | pdf-to-markdown output: read as source; §3.6 |
| UTF-8 text, `.tex` `.md` `.bib` `.sty` `.cls` | source | read directly; §3.4. A `.txt` is **not** assumed to be source: it may be an extraction |
| `%PDF-`, named `NAME_figures.pdf`, beside a transcription `NAME.md` | figures PDF | figure images of that transcription; §3.6. The profile reports it as `FIGURES PDF of …` |
| JPEG / PNG | single page image | image channel only |
| anything else | unknown | **stop and report**; do not guess |

**Q2 — Channels**: image yes/no, text yes/no. This fixes the regime:

| image | text | regime |
|---|---|---|
| yes | yes | standard: locate in text, read on image |
| yes | no | *image-only* (scanned PDF, no text layer): locate by viewing low-resolution pages, then crop. OCR (e.g. `tesseract`) may be used to **locate**, never to quote |
| no | yes | *unverified*: text is the only source; label all math unverified (§3.3). Not for source files or transcriptions (§3.4, §3.6) |
| no | no | nothing readable; report |

**Q3 — Failure modes of the text channel**: which of A, B, C (§4) are present.
They co-occur; record every one that applies, and apply the union of their
restrictions. The profile's `NOTE` lines flag suspects:

- many `ð`/`Þ` and equation tags like `ð40Þ` → substitution (A) suspect;
- `|…i` patterns → substituted closing angle bracket (A) suspect;
- U+21B5 or dropped-ligature words, or Private-Use characters inside prose
  words → substitution **in prose** (A) suspect;
- a high fraction of 1–2-character lines → geometry destruction (B) suspect;
- control bytes (`\x01`–`\x1f`) → font-slot leakage; map each on the image;
- `GlyphLessFont`, or a scanner/OCR producer string → OCR (C) suspect;
- fonts without ToUnicode maps, or Type 3 fonts → text set in those fonts may
  extract wrongly.

A suspect is a hypothesis. Confirm it by comparing one displayed equation, one
inline formula and one prose paragraph against the image before relying on it.

---

## 3. Access recipes

### 3.1 Paged ZIP archive (`N.jpeg` + `N.txt` + `manifest.json`)

- `unzip` (or `triage.py extract FILE --out DIR`) into a writable directory;
  `pdftotext`, `pdfinfo`, `pdftoppm`, `pdfplumber` do nothing useful on it.
- `manifest.json` lists pages, image paths and dimensions. Treat any
  "visual content" flag with suspicion until checked; it can be `true` on
  every page.
- Page `N` is `N.jpeg` / `N.txt`. Check whether the *printed* page equals `N`
  (§5) — often it does, sometimes with a fixed offset.
- Text layers commonly use CRLF line endings.

### 3.2 Genuine PDF

- `pdfinfo` (pages, producer), `pdffonts` (embedded fonts, Type 3, ToUnicode),
  `pdfimages -list` (raster images per page: a full-page image on every page
  suggests a scan).
- Text: `pdftotext -f N -l N FILE -` (reading order; avoid `-layout` for
  grepping, it interleaves columns). `triage.py extract` writes one `N.txt`
  per page for uniform grepping. A form feed `\f` separates pages in
  whole-document output.
- Image: `pdftoppm -r 200 -f N -l N -png FILE out`, or `triage.py crop`.
- No poppler: text via `pypdf` or `pdfplumber`; rendering via PyMuPDF (`fitz`).
  If nothing can render, the file is in the *unverified* regime until a
  renderer is available — say so.
- A LaTeX-produced PDF with proper ToUnicode maps usually has correct
  *characters* but still flattened geometry (mode B): superscripts on their own
  lines, big delimiters detached from their contents, evaluation bars dropped,
  and **drawn figures (TikZ, Feynman diagrams) absent from the text entirely**.

### 3.3 Text-only extraction (text disguised as `.pdf`)

- Read and grep directly; there is nothing to unzip and no image to consult.
- No page boundaries may exist; `\x0c` is often a glyph, not a page break.
  Locate pages by running headers (page number + chapter/section title);
  anchor on number *and* title, since equation lines can start with digits.
- Mixed line endings are common: strip `\r` before anchoring on `$`.
- Every equation taken from such a file is labelled *"text-layer reading,
  unverified"* and should be (a) cross-checked against the same object in an
  image-verifiable source, or (b) re-derived. Never settle a sign, bar,
  prime, dagger, sub/superscript or bra/ket from it alone. When the same
  formula exists in an image-verifiable file, cite that file for the formula
  and the text-only file for context.

### 3.4 Source files

`.tex` and `.md` are the ground truth for their own content and may be quoted
as-is, math included. A `.md` that opens with the transcription legend is a
pdf-to-markdown transcription; §3.6 says how to read it.

### 3.5 Viewing and cropping

A full page at native resolution is fine for prose and too small for
subscripts. Crop the line in question and upscale 2.5–4× with LANCZOS:

```bash
python3 SKILL_DIR/scripts/triage.py crop FILE --page 8 --box 55 150 480 330 --scale 3 --out /home/claude/c.png
```
then open the PNG with the `view` tool. `--box` is in pixels of the page
image (for a PDF, at `--dpi`, default 200); the command prints the page size.
On a two-column page, find the column gutter once and reuse it. For every
sign, index, prime, bar, fraction, or permutation subscript, crop *that
line*; resolve superscript vs subscript and numerator vs denominator
explicitly.

### 3.6 Markdown transcriptions (pdf-to-markdown)

**Recognition.** The first line is the legend
`<!-- Transcription of NAME.pdf. "page N" markers give the PDF page … -->`.
`triage.py profile` reports the container as `transcription` and counts its
page markers, `\tag`s and figure lines. The transcribed PDF can carry another
name in project knowledge (uploads rename files); the check matches them by
letters and digits only.

**Trust.** The transcription is read as source: quote it as-is, math
included, and label it by page (`transcription, p. N`), not as `verified` or
`unverified`. Do not re-check its equations against page images in the chat;
the point of converting is to spend those tokens once, at conversion time,
where every formula was transcribed from the image and proofread. Its LaTeX
keeps typeface distinctions (`\mathcal{G}` vs `G`, `\boldsymbol`), bars,
primes and tags as printed, apparent typos included.

**When to escalate.** Only in the following cases. Say what the
transcription says and ask the user for the original page. Do not correct it
silently or guess.
- A derivation, or a companion paper that restates the same object,
  contradicts it, and the conflict survives a re-check of the derivation.
- It is internally inconsistent: a tag missing or duplicated, a formula that
  does not parse, a sentence that breaks off.
- The profile reports a structural defect: missing or out-of-order page
  markers, a stray `<!-- continues -->`, a figures PDF that is not there.

**Pages.** `<!-- page N -->` opens page N of the PDF.
`<!-- page N (printed M) -->` adds the number printed on it. Where a
paragraph runs across a break, the marker stands inline at the break, so the
text after it is on page N. Without `(printed M)`, the printed number equals
N or was not determined at conversion; a project protocol records which.
Otherwise cite N and say it is the PDF page.
`triage.py grep PATTERN FILE` reports hits as `pN` or `pN(printed M)`, and
`triage.py text FILE N` prints page N.

**Equations.** Displays carry `\tag{N}` with the printed equation number, so
grep `\\tag\{12a\}`. In-text references keep the document's own style.

**Figures.** A figure is a placeholder line
`*[Fig. N: NAME_figures.pdf, page P]*` followed by its transcribed caption.
Text inside the figure (axis labels, legends, diagram labels) is not in the
Markdown. For any question about what a figure shows, open page P of the
figures PDF. Each figure there is labelled `Fig. N, p. S` or
`Fig. N, p. S (printed M)` (S its PDF page), and several figures share a page. Crop one with `triage.py crop` if
labels are small. The figures PDF has nothing else to triage.

**Beside the original.** If the transcribed PDF is also mounted, read the
transcription for content. Open the PDF only for questions about the page
itself (layout, an element the transcription omits).

---

## 4. Failure modes of the text channel

### Mode A — character substitution

**Mechanism.** A font is re-encoded, so glyphs extract as *other, legible*
characters. The damage looks like text, which is what makes it dangerous.

**Signature.** Unusual Latin-1 letters where delimiters belong (`ð…Þ` for
parentheses, `¼` for `=`), equation tags in the substituted form, kets closing
with `i`, ligatures turned into arrows, Private-Use characters or nothing.

**What is safe.** Prose set in an unaffected text font. Check: if prose
parentheses are ASCII while math parentheses are `ð…Þ`, only the math font is
remapped. If prose words are damaged (ligatures, `A\ue00biliations`), prose is
*not* automatically safe; repair it only when the completion is unique.

**Grep strategy.** Search for the *substituted* form of math tokens. An
equation's display tag uses the math font (`ð40Þ`), while in-prose
cross-references use the text font (`Eq. (40)`): grepping `(40)` finds
citations, not the definition.

**Traps.**
- Ordinary letters and digits can be remapped delimiters or symbols: `f g` for
  `{ }`, `h i j` for `⟨ ⟩ |`, `0` for a prime, `l` for `ℓ`. These are
  *two-valued* against real words and numbers.
- One control byte can stand for several unrelated glyphs in the same file.

*Illustration (Kugler et al., PRX 11, 041006 (2021), p. 15; mechanism only, not
a mapping for any other file):* `ci ∈ f\x04g` is cᵢ ∈ {±}; `Fσσ0` is F_{σσ′};
`2l` is 2^ℓ; and `\x02` is a line-break hyphen in `compo\x02nents`, a cdot in
`ω1\x02\x02\x02λ`, and a big parenthesis around the matrix of Eq. (75).

### Mode B — geometry destruction

**Mechanism.** Characters come out right; their *positions* do not.

**Signature.** Many 1–2-character lines; displayed equations split across
lines; matrices without rows.

**What is safe.** Prose; the identity of individual symbols (after checking a
sample); section headers; equation tags.

**Traps.**
- **False binary operations**: a flattened superscript reads as arithmetic.
  `p−1(η)` is p⁻¹(η); `β−1` is β⁻¹; `g 0` is g⁰. This is the most common
  misreading.
- **Accents, bars, hats, tildes dropped or detached**, and not uniformly within
  one expression: one bar survives as a free-standing `¯` before or after its
  index, the next vanishes.
- **Typeface distinctions erased**: calligraphic 𝒢 and roman G, bold **ω** and
  ω, 𝒯 and T can extract identically. Where the notation distinguishes them,
  the text layer silently merges two different objects.
- **Big delimiters detached** from their contents and **evaluation bars
  dropped** (`G(1,·) U 2` for G^{(1,·)}|_{U²}).
- **Control bytes are font-slot leakage** with per-document meaning (often big
  delimiters, Greek capitals, integral and sum signs, primes, relations). One
  byte can be several glyphs in one file: a hyphen, Σ and ∫, or ⟩, Θ and ∫.
- **Mathematical-alphanumeric Unicode** (italic 𝜔, bold 𝝎) is searchable only
  literally; Private-Use characters have no stable meaning.
- **Column order**: two-column pages usually extract left column fully, then
  right — but verify once per file; footers and running heads can splice into
  the middle of a hyphenated word.
- **Lost inter-word spaces** in tightly justified lines: search for one
  distinctive word, not a multi-word phrase.

### Mode C — OCR (probabilistic)

**Mechanism.** The text layer was produced by recognising a scan.

**Signature.** `GlyphLessFont`, scanner/OCR producer strings, a full-page raster
on every page, plausible-but-wrong words, digits confused with letters.

**Strategy.** Prose is no longer automatically safe and has no deterministic
repair: verify any prose sentence you quote on the image. Use fuzzy search
(distinctive words, partial matches) to locate. Mathematics is image-only, as
always.

**Co-occurrence.** A file can show A and B together (substituted kets inside
flattened equations), or A in prose and B in math. Record all modes present.

---

## 5. Page numbering

Printed page numbers and file page indices differ more often than expected.

1. Run `triage.py profile`; read the `folio` lines. Each pattern (e-locator
   `041006-N`, `(N of T)`, `- N -`, footer or running-head numbers) reports the
   dominant offset, how many pages agree, and which disagree or lack a match.
2. If one pattern agrees on all pages, the offset is verified exhaustively.
   Otherwise confirm the offset on the image at no fewer than three spread
   pages, and note unnumbered pages (openers, figure pages).
3. Watch for segments: front matter, appendices or an index can carry a
   different offset or none.
4. Text-only files: use running headers (`running_headers` in the profile);
   they are noisy, so confirm a located page by its section title.
5. Transcriptions: the page markers give the PDF page and, where it differs,
   the printed page (§3.6); nothing to measure.

---

## 6. Workflow: locate → read → quote

**Locate (text channel).**
- Grep for a distinctive *prose* word or phrase; section headers are usually
  clean.
- For an equation's definition, grep its tag in the form the file uses (ASCII
  `(146a)`, substituted `ð40Þ`, bracketed `[1]`, or `\tag{1}` in a
  transcription). Know the citation style too:
  some journals tag equations `[N]` and cite references `(N)`.
- `triage.py grep PATTERN FILE... [--escape]` reports `file:pPAGE:LINE`, strips
  `\r`, and with `--escape` shows control bytes as `\xNN`.
- `triage.py text FILE N --escape` dumps one page with damage visible.

**Read (image channel).** Open the page; crop every line that carries a
sign, index or accent (§3.5). When still in doubt, cross-check the same object
where it reappears — later in the same document, or in a companion paper that
restates it.

**Quote.**
- Prose may be quoted from the text layer after deterministic repairs
  (line-break hyphen bytes → `-` or joined; ligature damage with a unique
  completion), except under mode C.
- Mathematics is quoted from the image, from source, or from a
  transcription (§3.6); anything else is labelled unverified.
- Cite as "Author Year, p. N, Eq. (X)" with N the printed page.

---

## 7. Establishing a glyph mapping

1. Find the glyph in the text layer (`grep --escape`).
2. Locate the same spot on the image and crop it.
3. Record `X = Y, verified at p. N (context)`.
4. Test multi-valuedness: sample at least three contexts of different kinds
   (prose, inline math, display math, delimiters). If they disagree, record
   every meaning with its context.
5. Anything inferred from context alone is `provisional`. For a text-only file
   that is the best available; say so.
6. Never apply a mapping from one file to another.

---

## 8. Tool fallbacks

| need | first choice | fallback | none available |
|---|---|---|---|
| container | `triage.py profile` | `head -c 8 FILE \| od -c` | — |
| PDF text | `pdftotext` | `pypdf`, `pdfplumber` | image-only regime |
| PDF image | `pdftoppm` | PyMuPDF | unverified regime; say so |
| crop | `triage.py crop` (Pillow) | view whole page | view whole page, flag low confidence |
| fonts | `pdffonts` | `pypdf` font resources | skip; rely on image checks |
| OCR (locate only) | `tesseract` | — | view pages sequentially |
