import json
import re
from collections import defaultdict

LINE = re.compile(r'^(\S+) \S+ \S+ \[[^\]]*\] "(\S+) (\S+)[^"]*" (\d{3}) ')

hits = defaultdict(list)
with open("access.log") as f:
    for line in f:
        m = LINE.match(line)
        if m and m.group(4) == "404":
            hits[m.group(1)].append(m.group(3))

ranked = sorted(hits.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:5]
top = [{"ip": ip, "count": len(p), "paths": sorted(set(p))} for ip, p in ranked]
print(json.dumps({"top": top}))
