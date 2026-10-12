---
name: pdf-to-markdown
description: Convert a PDF (papers, notes, textbooks with equations) to text-only Markdown with exact LaTeX math, plus one companion PDF of its figures, machine-checked. Use when asked to convert a PDF to .md.
metadata:
  version: "2.5"
---

# PDF → Markdown with exact math

`SKILL_DIR` below is this skill's folder (usually `/mnt/skills/user/pdf-to-markdown`).
Work in `/home/claude/work`.

**Output naming.** `NAME` is the original PDF's file name without `.pdf`, exactly
as uploaded (same characters, case, spaces and underscores; never shortened or
tidied). The deliverables are `NAME.md`, a text-only Markdown file with no image
data in it and a page marker at the start of every page (so answers drawn from it
can cite pages), and `NAME_figures.pdf`, all figures packed several per page so that
every figure stays legible (at least 150 dpi effective when Claude views a page)
at the lowest token cost. A document without figures gets no figures PDF. Both
files upload directly to a Project; the figures PDF can be left out when no
figure needs to be seen, since every caption is in the Markdown.

## Ground rules (learned from testing)

- **Never take mathematics from the text layer.** It merges calligraphic/roman/bold
  (𝒢 → G, **ω** → ω), detaches accents (K̃ came out as `K = 1 ˜ /Ω`), flattens
  sub/superscripts, and leaks `(cid:NN)` for ∫ ∑ and braces. Every formula,
  inline or displayed, is transcribed from the page image.
- **Do not use markitdown on PDFs.** On a LaTeX PDF it invented tables out of
  ordinary sentences.
- **Do not read the text layer.** Prose read from the strips is reliable. When one
  word is doubtful, `grep` for it in `page_NNN.txt`; never `cat` or `view` a whole
  page of it.
- **Every token of output is written once.** Each page goes to its own file;
  the document is joined by a script; corrections are targeted edits. Never
  re-output the document or a page in the chat or in a new file.
- **If the LaTeX source exists, use it instead** (`pandoc -f latex -t markdown`),
  then fix `\bm`→`\boldsymbol`, drop `\label`, add `\tag{}`s and the title/abstract.

## Steps

1. `pip install pymupdf --break-system-packages -q` (if missing), then
   `python3 SKILL_DIR/scripts/prepare.py INPUT.pdf /home/claude/work`.
   It renders 170 dpi strips `page_NNN_sKK.png`, cut between lines, and prints
   one line per page: whether the page needs images (`img`) or may come from the
   text layer (`text-ok`, no math fonts at all), each strip with its y-range in
   points, and the printed equation tags (a tag is found flush with the right edge
   of its own text column, so both columns of a two-column layout are covered;
   an inline reference such as "Eq. (7)" is not a tag). Where the page number printed on a page
   differs from its PDF page number (a journal article, a book chapter), the line
   reads `pN (printed M):`, and the last line says where those numbers came from
   (PDF page labels, or one offset found in headers/footers). Glance at the first
   strip of a page or two to confirm them; if they are wrong, note the right offset
   for step 4. That printout is all you need; do not open `manifest.json` (the
   check scripts and `assemble.py` read it).

   Then extract the figures:
   `python3 SKILL_DIR/scripts/figures.py INPUT.pdf /home/claude/work`
   It finds each figure from its caption ("Fig. N", "Figure N", "FIG. N" followed by
   ".", ":", "|" or a dash, so running text such as "Figure 1(a) shows" is not a
   caption), keeps the crop inside the caption's column, leaves out page numbers
   and running heads, trims it to what is actually drawn, and renders the whole
   region (vector art and embedded images together, at 200 dpi) to
   `figures/figN.png`, and writes `figures/check_figN.png`: the surroundings at low
   resolution with the crop drawn as a red box. `view` each check image (or a
   montage of several) and confirm that nothing of the figure lies outside the box
   and no running text lies inside it. If a crop is wrong, or a figure has no
   "Fig." caption, render that region yourself with PyMuPDF to `figures/<name>.png`.
2. For each page, `view` its strips in order and write that page's Markdown with
   `create_file` to `/home/claude/work/md/page_NNN.md` (three-digit page number).
   Where a symbol is small or ambiguous, render a zoom (500–600 dpi) of just that
   region: `page.get_pixmap(dpi=600, clip=pymupdf.Rect(x0,y0,x1,y1))`, coordinates
   in points as printed by `prepare.py`. Always zoom for: bars spanning several
   characters (`\overline{i+1}` vs `\bar i+1`), tildes and hats, primes, which
   terms an under/overbrace covers (including a leading minus sign), bold vs not
   bold, and calligraphic vs roman vs italic letters.
3. Writing conventions:
   - Inline `$...$`, display `$$ ... \tag{N} $$` using the **printed** number
     (tags can be out of sequence, e.g. (33) after (8)). Display blocks on their
     own lines, blank line before and after.
   - Reproduce typeface exactly: `\mathcal{G}`, `\mathrm{G}`, `\boldsymbol\omega`,
     upright `\mathrm i`, `\mathrm d`, `\mathrm e` when the PDF prints them upright.
   - Only KaTeX/MathJax-compatible commands; no custom macros. `\boxed{}`,
     `\underbrace{}_{}`, `\begin{cases}` and `\tag{}` are fine.
   - Headings as `#`/`##`/`###`; bold run-in paragraph heads as `**...**`.
   - Page numbers are added by script. Never write page markers, printed page
     numbers, running heads or footers into a page file. Every page gets a file,
     even one with nothing to transcribe (leave it empty), so its marker exists.
   - A page that ends mid-paragraph ends its file with the line
     `<!-- continues -->`; the next file starts with the rest of the sentence.
     A word hyphenated across the break is written whole on the earlier page.
   - Figures: where a figure stands, write `![Fig. N](figure:figN)` on its own
     line, then the caption as a paragraph starting `**Fig. N.**`, transcribed
     from the strips like any other text. Do not transcribe text inside the figure
     (axis labels, legends); it is part of the image. Never write image data,
     file names or page numbers yourself: `assemble.py` turns each placeholder
     into a line `*[Fig. N: NAME_figures.pdf, page P]*` naming where it is.
   - Reproduce the document as printed, including apparent typos; do not correct.
4. Join the pages, then run the mechanical checks:
   `python3 SKILL_DIR/scripts/assemble.py /home/claude/work/md /home/claude/work/out --name "NAME"`
   `python3 SKILL_DIR/scripts/check.py "/home/claude/work/out/NAME.md" /home/claude/work/manifest.json`
   `assemble.py` writes `out/NAME.md` and `out/NAME_figures.pdf`. It opens the
   Markdown with a one-line legend and starts every page with `<!-- page N -->`,
   or `<!-- page N (printed M) -->` when the printed number differs (N is the PDF
   page); where a paragraph runs across the break the marker stands inline at the
   break. If the printed numbers from step 1 were wrong, add `--printed-offset K`
   (printed = N + K) or `--printed-offset none`. It places the
   figures at native size in order of appearance, adding them to a page until
   the page would fall below 150 dpi effective (about 50 square inches, long edge
   about 10 inches), labels each "Fig. N", and replaces every placeholder with
   the line naming its page; in the figures PDF each label also names the
   document page the figure comes from. It prints each page's figures and effective
   resolution; a WARNING line means one figure is too large for any page and is
   below the floor on its own (report it, do not shrink it). It stops with an
   error if a placeholder has no image. `check.py` tests the KaTeX syntax of every formula, that every printed
   equation tag is present exactly once (a `\tag` whose "(N)" is in the text layer
   but was not detected as a tag is listed for a check by eye, not failed), that no text-layer debris such as
   `(cid:NN)` remains, and that every PDF page has exactly one marker, in order. Fix each finding with `str_replace` on `out/NAME.md`; do
   not rewrite the file.
5. Proofread displayed equations:
   `python3 SKILL_DIR/scripts/verify_eqs.py "/home/claude/work/out/NAME.md" /home/claude/work`
   Read its full printout first: any `PROBLEM` line is an equation that is not on
   the sheets and must be fixed. Then `view` each `verify/sheet_NN.png`. Each
   panel shows the PDF crop (top: the equation's own column, between the nearest
   prose lines; it may include one short neighbouring line) and the re-typeset
   transcription (bottom).
   Compare symbol by symbol and fix any difference with `str_replace`. Inline
   math is not covered by the sheets: re-read it on the strips for any line with
   indices or accents.
6. Copy `out/NAME.md` and, if it exists, `out/NAME_figures.pdf` to
   `/mnt/user-data/outputs/` and present them in one `present_files` call,
   `NAME.md` first. Never deliver loose image files. Report in one or two lines:
   pages done (with the printed page range, if any), figures and figures-PDF pages, check results, and any symbol left
   ambiguous (say where).

## Budget

Figures cost almost nothing here: they are packed by script, and each crop check is a
few hundred tokens (a montage of several is cheaper). Each strip or zoom costs
context: a 170 dpi strip is about 600 tokens, so a
page of 4–5 strips is about 2,500–3,000 tokens, plus zooms and the proofreading
sheets (about 1,500 tokens each, four equations per sheet). A 10-page note fits
easily; for a long paper or book, convert one chapter or section per
conversation and say so up front.

## Regression test (when a .tex is available)

`scripts/eval/mathcmp.py SOURCE.tex NAME.md [--lenient]` compares every display
and inline formula token by token (after expanding zero-argument `\newcommand`s;
`--lenient` also forgives upright vs italic i, d, e). Count exact matches only;
the mean similarity stays high even when formulas are wrong. It works on any
tool's Markdown output, not just this skill's;
`scripts/eval/prosecmp.py SOURCE.tex NAME.md` compares prose word by word.
Remaining differences are often spelling-only (`F_{\rm rest}` vs
`F_\mathrm{rest}`, `$\Rightarrow$` vs `⇒`); judge each one.
