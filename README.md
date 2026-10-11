<div align="center">

# 🛡️ SRT521 — Network Attack Analysis

**AI-assisted security log analysis: orchestrating LLM coding agents and building a tool-calling agent from scratch**

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Linux](https://img.shields.io/badge/WSL-Ubuntu_24.04-E95420?logo=ubuntu&logoColor=white)
![LLM Agents](https://img.shields.io/badge/LLM-Agents-8A2BE2)
![Status](https://img.shields.io/badge/checks-all_passing-brightgreen)

</div>

---

## 📌 Overview

Coursework from **SRT521 (Fall 2026, Seneca Polytechnic)**. Each lab answers a real security question, such as *"Which IP is brute-forcing SSH?"*, from raw log files (`access.log`, `firewall.log`, `auth.log`). LLM agents do the analysis under controlled conditions. The focus is on **safe agent design**: permission gates, task boundaries, verifiable outputs and token budgets.

## 🔬 Labs

| # | Lab | What I did | Key result |
|---|---|---|---|
| 01 | [**Coordinating Two AI Agents**](lab01/README.md) | Ran Claude and Gemini in parallel, coordinated through a file-based mailbox with fallback logic | 3 of 3 validation checks **PASS** |
| 02 A | [**Building a Tool-Calling Agent**](lab02/partA/README.md) | Wrote a ReAct agent in Python with a permission-gated `run_shell` tool and JSON-schema-validated answers | Found the top SSH brute-force source; **17 of 17** checks passed |
| 02 B | [**Context Management**](lab02/partB/README.md) | Added output clipping and a sliding context window to the agent loop | Input tokens cut **31,192 → 7,528 (−76%)** |

## 🧠 Highlights

- **A custom agent in [`agent/`](agent/):** an OpenAI-compatible client, a step loop, a tool registry with a human approval gate (`[gate] y/n`), JSON transcripts, and a schema-retry fallback.
- **Clipping:** tool results over 3,000 characters keep the first 2,000 and last 800 characters, with an `[... N characters elided ...]` marker. The JSON stays valid and error text is never clipped.
- **Sliding window:** only the 3 newest tool results are sent to the model. The full history stays in the transcript for auditing.
- **Multi-agent hand-off:** independent work runs in parallel, dependent work polls for a done message, and explicit fallbacks cover a missing or invalid upstream result.

## 🗂️ Repository structure

```
agent/          Tool-calling agent: client.py, loop.py, tools.py, prompts.py
lab01/          Plan, task briefs, agent-written scripts and outputs, mailbox hand-offs
lab02/partA/    Agent build, custom rules run, transcripts
lab02/partB/    Clip and window changes, before/after transcripts
```

## ▶️ Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
export SRT521_API_BASE="https://..."  SRT521_API_KEY="..."  SRT521_MODEL="..."
python3 -m agent "Which source IP had the most failed SSH password attempts?" \
    --data lab02/partA/data --tools run_shell --transcript out.json
python3 lab02/partA/show.py out.json        # readable trace with token counts
```

## 🧰 Tools and skills

`Python` · `Linux / WSL` · `tmux` · `Git` · `Log analysis` · `LLM tool calling` · `Prompt and context engineering` · `Claude` · `Gemini`

---

<sub>Author: <b>Rabbi Muhammad Aman</b> · Academic coursework. All analysis was done on lab-provided sample logs. Starter-kit files (checkers, specs, examples) were provided by the course.</sub>
