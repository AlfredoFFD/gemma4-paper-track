import io
import sys

p = sys.argv[1]
s = io.open(p, encoding='utf-8', newline='').read()
nl = '\r\n' if '\r\n' in s else '\n'
a = "[EXPERIMENT]  # E and H re-run as same-platform references"
assert s.count(a) == 1
s = s.replace(a, a + nl + "if os.environ.get('ARMS'):" + nl
              + "    ARMS = os.environ['ARMS'].split(',')  # optional override; unset = the experiment's list")
b = "open(INPUTS / 'states.jsonl', encoding='utf-8')"
assert s.count(b) == 1
s = s.replace(b, "open(INPUTS / os.environ.get('STATES_FILE', 'states.jsonl'), encoding='utf-8')")
io.open(p, 'w', encoding='utf-8', newline='').write(s)
print('patched')
