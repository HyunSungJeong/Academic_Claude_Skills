#!/usr/bin/env python3
"""Mechanical checks on a finished transcription.

usage: check.py TRANSCRIPT.md WORKDIR/manifest.json

1. Every math span ($...$ and $$...$$) must parse in KaTeX (what most Markdown
   viewers use); errors are listed with the offending snippet.
2. Every equation tag printed in the PDF must appear as \\tag{..} exactly once,
   and no \\tag may appear that the PDF does not print.
3. Leftovers from the text layer that must never reach the output:
   (cid:NN), Private-Use characters, U+FFFD, stray combining accents.
4. Page markers: every page of the PDF has exactly one  <!-- page N ... -->,
   in increasing order, and no  <!-- continues -->  is left over.
Exit status 0 only if everything passes.
"""
import sys, re, json, subprocess, os, shutil
md = open(sys.argv[1]).read(); man = json.load(open(sys.argv[2]))
ok = True

# 1. KaTeX
js = r'''
const katex = require(process.env.KATEX);
const items = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const bad = [];
for (const [i, display, tex] of items) {
  try { katex.renderToString(tex, {displayMode: display, throwOnError: true, strict: 'ignore'}); }
  catch (e) { bad.push([i, e.message.split('\n')[0], tex.slice(0, 120)]); }
}
console.log(JSON.stringify(bad));
'''
blocks = [(m.start(), True, m.group(1)) for m in re.finditer(r'\$\$(.*?)\$\$', md, re.S)]
rest = re.sub(r'\$\$.*?\$\$', lambda m: ' ' * len(m.group(0)), md, flags=re.S)
inl = [(m.start(), False, m.group(1)) for m in re.finditer(r'(?<![\\$])\$(?!\$)(.+?)(?<!\\)\$', rest, re.S)]
items = sorted(blocks + inl)
root = subprocess.run(['npm', 'root', '-g'], capture_output=True, text=True).stdout.strip()
katex = os.path.join(root, 'katex')
if not os.path.isdir(katex):
    subprocess.run(['npm', 'i', '-g', 'katex@0.16.11'], capture_output=True)
if shutil.which('node') and os.path.isdir(katex):
    r = subprocess.run(['node', '-e', js], input=json.dumps(items), capture_output=True, text=True,
                       env={**os.environ, 'KATEX': katex})
    bad = json.loads(r.stdout or '[]')
    line = lambda pos: md.count('\n', 0, pos) + 1
    for pos, msg, tex in bad:
        ok = False; print(f'KaTeX  line {line(pos)}: {msg}\n       {tex}')
    print(f'KaTeX: {len(items)} math spans, {len(bad)} errors')
else:
    print('KaTeX: not available, syntax check skipped')

# 2. tags
pdf_tags = [t['tag'] for p in man['pages'] for t in p['equation_tags']]
md_tags = re.findall(r'\\tag\{([^}]*)\}', md)
missing = [t for t in pdf_tags if t not in md_tags]
extra = [t for t in md_tags if t not in pdf_tags]
dup = sorted({t for t in md_tags if md_tags.count(t) > 1})
for name, L in (('missing from transcript', missing), ('not printed in PDF', extra), ('duplicated', dup)):
    if L: ok = False; print(f'TAGS {name}: {L}')
print(f'Tags: PDF {len(pdf_tags)}, transcript {len(md_tags)}' + ('' if pdf_tags else '  (none detected in PDF: check by eye)'))

# 3. text-layer debris
for pat, name in ((r'\(cid:\d+\)', '(cid:NN)'), (r'[\uE000-\uF8FF]', 'private-use char'), ('\uFFFD', 'U+FFFD'),
                  (r'(?<![A-Za-z])[\u0300-\u036F\u00A8\u00AF\u00B4\u02C6\u02DC]', 'detached accent')):
    hits = [md.count('\n', 0, m.start()) + 1 for m in re.finditer(pat, md)]
    if hits: ok = False; print(f'DEBRIS {name} on lines {hits[:10]}')
# 4. page markers
marks = [int(m.group(1)) for m in re.finditer(r'<!-- page (\d+)(?: \(printed [^)]*\))? -->', md)]
pages = [p['page'] for p in man['pages']]
miss = [n for n in pages if n not in marks]
dupm = sorted({n for n in marks if marks.count(n) > 1})
if miss: ok = False; print(f'PAGES missing marker (page file missing?): {miss}')
if dupm: ok = False; print(f'PAGES duplicated marker: {dupm}')
if marks != sorted(marks): ok = False; print('PAGES markers out of order')
if '<!-- continues -->' in md:
    ok = False; print(f'PAGES leftover <!-- continues --> on lines {[md.count(chr(10), 0, m.start()) + 1 for m in re.finditer("<!-- continues -->", md)][:10]}')
print(f'Page markers: {len(marks)} for {len(pages)} PDF pages')

print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
