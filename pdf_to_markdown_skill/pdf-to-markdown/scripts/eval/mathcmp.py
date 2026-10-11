"""Compare math in a Markdown transcription against LaTeX source, token by token.
usage: mathcmp.py SOURCE.tex TRANSCRIPT.md [--lenient]
--lenient forgives upright vs italic i, d, e (typeface only); bold spellings,
^{\\prime} vs ', \\overline vs \\bar on one character are always forgiven."""
import re, sys, difflib

def macros(tex):
    """collect zero-argument \\newcommand definitions"""
    m = {}
    for name, body in re.findall(r'\\newcommand\{\\(\w+)\}\{((?:[^{}]|\{[^{}]*\})*)\}', tex):
        m[name] = body
    return m

def expand(s, m):
    for _ in range(5):
        s = re.sub(r'\\([A-Za-z]+)', lambda x: m.get(x.group(1), x.group(0)) if x.group(1) in m else x.group(0), s)
    return s

SPACING = {r'\,', r'\;', r'\!', r'\ ', r'\:', r'\quad', r'\qquad', r'\displaystyle', r'\textstyle',
           r'\left', r'\right', r'\Bigl', r'\Bigr', r'\bigl', r'\bigr', r'\Big', r'\big', r'\Bigg', r'\bigg', r'\hfill'}
ALIAS = {r'\mathbf': r'\boldsymbol', r'\pmb': r'\boldsymbol', r'\overline1': None, r'\tfrac': r'\frac', r'\dfrac': r'\frac', r'\bm': r'\boldsymbol', r'\dots': r'\cdots', r'\ldots': r'\cdots',
         r'\rm': r'\mathrm', r'\neq': r'\ne', r'\ge': r'\geq', r'\le': r'\leq', r'\to': r'\rightarrow'}

LENIENT = '--lenient' in sys.argv
def tokens(s):
    s = re.sub(r'\\avg\{((?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*)\}', r'\\langle \1\\rangle', s)
    s = re.sub(r'\\label\{[^}]*\}|\\tag\{[^}]*\}|\\nonumber', '', s)
    s = re.sub(r'\\(?:eq)?ref\{[^}]*\}', 'REF', s)
    s = s.replace('~', ' ')
    s = re.sub(r'\{\\rm\s+([^{}]*)\}', r'\\mathrm{\1}', s)      # {\rm x} -> \mathrm{x}
    s = re.sub(r'\\\n', ' ', s)                                   # backslash-newline = control space
    s = s.replace('&', '')
    s = re.sub(r"\^\{?\\prime\}?", "'", s)                      # ^{\prime} -> '
    s = re.sub(r"\^\{?\\prime\\prime\}?", "''", s)
    toks = re.findall(r'\\[A-Za-z]+|\\.|[^\s]', s)
    out = []
    for t in toks:
        if t in SPACING: continue
        t = ALIAS.get(t, t)
        out.append(t)
    # F_{\rm rest} -> F_{\mathrm rest}; normalise {\mathrm x} vs \mathrm{x} not handled: rare
    # drop braces around single tokens:  {x} -> x  (then the loop below)
    changed = True
    while changed:
        changed = False
        for i in range(len(out) - 2):
            if out[i] == '{' and out[i+2] == '}' :
                out[i:i+3] = [out[i+1]]; changed = True; break
    # \overline{x} on a single token is the same mark as \bar x
    out = [r'\bar' if t == r'\overline' and i + 1 < len(out) and out[i+1] not in '{' else t for i, t in enumerate(out)]
    if LENIENT:  # forgive upright vs italic i, d, e only
        out = [t for i, t in enumerate(out) if not (t == r'\mathrm' and i + 1 < len(out) and out[i+1] in ('i', 'd', 'e'))]
    return out

def tex_math(tex):
    body = tex.split(r'\begin{document}')[1]
    blocks = []
    for env in re.finditer(r'\\begin\{(equation|align)\*?\}(.*?)\\end\{\1\*?\}', body, re.S):
        parts = re.split(r'\\\\(?:\[[^\]]*\])?', env.group(2)) if env.group(1) == 'align' else [env.group(2)]
        for p in parts:
            blocks.append(p.replace('&', ''))
    inline = re.findall(r'(?<!\\)\$(.+?)(?<!\\)\$', re.sub(r'\\begin\{(equation|align)\*?\}.*?\\end\{\1\*?\}', '', body, flags=re.S), re.S)
    return blocks, inline

def md_math(md):
    blocks = re.findall(r'\$\$(.*?)\$\$', md, re.S)
    rest = re.sub(r'\$\$.*?\$\$', '', md, flags=re.S)
    inline = re.findall(r'(?<!\\)\$(.+?)(?<!\\)\$', rest, re.S)
    return blocks, inline

def sim(a, b):
    return difflib.SequenceMatcher(a=a, b=b, autojunk=False).ratio()

def align(src, out):
    """monotone alignment maximising total similarity; a source formula may also match
    the concatenation of 2-3 consecutive transcript formulas (tools that split equations)"""
    n, m = len(src), len(out)
    best = [[0.0] * (m + 1) for _ in range(n + 1)]; back = [[None] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        for j in range(m + 1):
            if i == 0 and j == 0: continue
            cands = []
            if i: cands.append((best[i-1][j], ('skip_src', 1, 0)))
            if j: cands.append((best[i][j-1], ('skip_out', 0, 1)))
            for k in (1, 2, 3):
                if i and j >= k:
                    joined = sum(out[j-k:j], [])
                    r = sim(src[i-1], joined)
                    if r > 0.5: cands.append((best[i-1][j-k] + r, ('match', 1, k)))
            best[i][j], back[i][j] = max(cands, key=lambda c: c[0])
    pairs, i, j = [], n, m
    while i or j:
        op, di, dj = back[i][j]
        if op == 'match': pairs.append((i-1, list(range(j-dj, j))))
        elif op == 'skip_src': pairs.append((i-1, []))
        i, j = i - di, j - dj
    return sorted(p for p in pairs)

def report(src, out, kind, verbose=True):
    pairs = align(src, out); exact = 0; total = 0.0; lines = []
    for i, js in pairs:
        if not js:
            lines.append(f'--- {kind} #{i+1}: MISSING  src: {"".join(src[i])[:100]}'); continue
        b = sum((out[j] for j in js), []); r = sim(src[i], b); total += r
        if r == 1.0: exact += 1; continue
        lines.append(f'--- {kind} #{i+1}  similarity {r:.3f}' + (f'  (matched {len(js)} transcript pieces)' if len(js) > 1 else ''))
        sm = difflib.SequenceMatcher(a=src[i], b=b, autojunk=False)
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op != 'equal':
                lines.append(f'   {op:7s} …{"".join(src[i][max(0,i1-6):i1])}|  src: {"".join(src[i][i1:i2])!r}  md: {"".join(b[j1:j2])!r}')
    if verbose: print('\n'.join(lines))
    return exact, total / max(1, len(src)), len(src)

args = [a for a in sys.argv[1:] if not a.startswith('--')]
tex = open(args[0]).read(); md = open(args[1]).read()
m = macros(tex)
tb, ti = tex_math(tex); mb, mi = md_math(md)
tb = [tokens(expand(x, m)) for x in tb]; ti = [tokens(expand(x, m)) for x in ti]
mb = [tokens(x) for x in mb]; mi = [tokens(x) for x in mi]
# a tool may set an inline formula as display or vice versa: score each source class against all output math
allout = sorted(mb + mi, key=lambda t: md.find(''.join(t)[:10]))
print(f'math spans: source {len(tb)} display + {len(ti)} inline;  transcript {len(mb)} display + {len(mi)} inline\n')
ed, sd, nd = report(tb, mb, 'display')
ei, si, ni = report(ti, mi, 'inline')
print(f'\nSCORE display: {ed}/{nd} exact, mean token similarity {sd:.3f}')
print(f'SCORE inline : {ei}/{ni} exact, mean token similarity {si:.3f}')
