# Task 2 spec, second half: make_report.py

Input: `alpha/output.json` (task 1's result) and `beta/blocked.json` (the first half of task 2). Read nothing else; in particular, do not read `access.log` or `firewall.log` again.

Program: `beta/make_report.py`, Python 3.11, standard library only. It runs from `lab01/` as `python3 beta/make_report.py > beta/report.json`.

Output: one JSON object.

```json
{"block": ["..."], "already_blocked": ["..."], "top_port": N}
```

- `block` holds the `ip` of every entry in alpha's `top` that does not appear in beta's `sources`, in alpha's order: the probing addresses the firewall has not blocked yet.
- `already_blocked` holds the `ip` of every entry in alpha's `top` that does appear in beta's `sources`, in alpha's order.
- `top_port` is the `port` of the first entry in beta's `ports`: the port with the most blocked attempts.

Check, from `lab01/`: `python3 check.py --report beta/report.json`. The checker recomputes both inputs from the data files, so a wrong `output.json` or `blocked.json` shows up here as well.
