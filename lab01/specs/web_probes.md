# Task 1 spec: web_probes.py

Input: `access.log` in `lab01/`, a 150-line synthetic sample of a web server's access log in the combined format (`IP - - [date] "METHOD /path HTTP/1.1" STATUS BYTES "-" "AGENT"`). Read no other data file.

Program: `alpha/web_probes.py`, Python 3.11, standard library only. It runs from `lab01/` as `python3 alpha/web_probes.py > alpha/output.json` and reads `access.log` from the current directory.

Output: one JSON object.

```json
{"top": [{"ip": "...", "count": N, "paths": ["..."]}]}
```

- `top` holds the five client IPs with the most responses of status 404, most first, ties broken by IP address ascending (string order).
- A line counts when its status code is `404`, whatever the method or the path. No other status counts.
- `count` is the number of such lines for that IP.
- `paths` is the list of distinct request paths (the second word inside the quoted request) among that IP's 404 lines, sorted.

Check, from `lab01/`: `python3 check.py alpha/output.json`.
