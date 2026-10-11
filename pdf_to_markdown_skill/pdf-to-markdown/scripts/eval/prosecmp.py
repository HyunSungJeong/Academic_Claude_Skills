"""Word-level prose diff (math removed) between LaTeX source and Markdown transcript."""
import re, sys, difflib
tex = open(sys.argv[1]).read().split(r'\begin{document}')[1]; md = open(sys.argv[2]).read()
def strip_tex(s):
    s = re.sub(r'(?<!\\)%.*', '', s)
    s = re.sub(r'\\begin\{(equation|align)\*?\}.*?\\end\{\1\*?\}', ' ', s, flags=re.S)
    s = re.sub(r'(?<!\\)\$.*?(?<!\\)\$', ' ', s, flags=re.S)
    s = re.sub(r'\\(?:eq)?ref\{[^}]*\}', 'N', s); s = re.sub(r'\\label\{[^}]*\}', '', s)
    s = s.replace('``', '"').replace("''", '"').replace('---', '—').replace('--', '–').replace('~', ' ').replace(r'\&', '&')
    s = re.sub(r'\\(?:begin|end)\{[^}]*\}(\[[^\]]*\])?', ' ', s)
    s = re.sub(r'\\[A-Za-z]+\*?', ' ', s); s = re.sub(r'[{}\\]', ' ', s)
    return s
def strip_md(s):
    s = re.sub(r'<!--.*?-->', ' ', s, flags=re.S)          # page markers and other comments
    s = re.sub(r'\$\$.*?\$\$', ' ', s, flags=re.S); s = re.sub(r'(?<!\\)\$.*?(?<!\\)\$', ' ', s, flags=re.S)
    s = re.sub(r'\((\d+)\)', '(N)', s)
    s = re.sub(r'[#*_]', ' ', s); return s
def words(s): return re.findall(r"[A-Za-z][A-Za-z'’\-]*", s.replace('’', "'"))
a = words(strip_tex(tex)); b = words(strip_md(md))
sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
print(f'prose words: source {len(a)}, transcript {len(b)}, similarity {sm.ratio():.4f}')
for op,i1,i2,j1,j2 in sm.get_opcodes():
    if op!='equal': print(f'  {op:7s} src {" ".join(a[i1:i2])!r:40s} md {" ".join(b[j1:j2])!r}   (…{" ".join(a[max(0,i1-4):i1])})')
