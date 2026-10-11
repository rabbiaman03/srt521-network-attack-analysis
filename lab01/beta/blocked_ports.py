import json
import re
from collections import Counter

def main():
    port_counts = Counter()
    sources = []
    seen_sources = set()

    src_re = re.compile(r'\bSRC=(\S+)')
    dpt_re = re.compile(r'\bDPT=(\d+)')

    with open("firewall.log", "r", encoding="utf-8") as f:
        for line in f:
            if "[UFW BLOCK]" not in line:
                continue

            src_match = src_re.search(line)
            if src_match:
                src = src_match.group(1)
                if src not in seen_sources:
                    seen_sources.add(src)
                    sources.append(src)

            dpt_match = dpt_re.search(line)
            if dpt_match:
                port = int(dpt_match.group(1))
                port_counts[port] += 1

    sorted_ports = sorted(
        [{"port": p, "blocked": c} for p, c in port_counts.items()],
        key=lambda x: (-x["blocked"], x["port"])
    )

    output = {
        "ports": sorted_ports,
        "sources": sources
    }

    print(json.dumps(output, indent=2))

if __name__ == "__main__":
    main()
