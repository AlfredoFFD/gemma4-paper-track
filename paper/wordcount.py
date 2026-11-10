"""Word count of the paper's main text, section by section.

Usage: py -I -X utf8 paper/wordcount.py [paper/draft.md]
Counted: everything from "## Abstract" up to "## References" (headings, figure and table captions included).
Not counted: the title and subtitle, HTML comments, image lines, the reference list and the appendix (the host has
said that references do not count and that an appendix is supplementary).
A word is a run of characters between spaces that contains a letter or a digit.
"""
import re
import sys

path = sys.argv[1] if len(sys.argv) > 1 else 'paper/draft.md'
text = open(path, encoding='utf-8').read()
text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
start = text.index('## Abstract')
end = text.index('## References')
main = text[start:end]
total = 0
section, counts = None, []
for line in main.splitlines():
    if line.startswith('![]('):
        continue
    if line.startswith('## '):
        section = line[3:].strip()
        counts.append([section, 0])
    n = sum(1 for w in line.split() if re.search(r'[A-Za-z0-9]', w))
    counts[-1][1] += n
    total += n
for name, n in counts:
    print(f'{n:5d}  {name}')
print(f'{total:5d}  MAIN TEXT (limit 3,000)')
rest = text[end:]
print(f'{sum(1 for w in rest.split() if re.search(r"[A-Za-z0-9]", w)):5d}  references and appendix (not counted)')
