# SRT521 — Network Attack Analysis (AI-Assisted Security Analysis)

Coursework for SRT521 at Seneca Polytechnic (Fall 2026). This course uses **LLM coding agents and a hand-built tool-calling agent** to analyze security logs: web probes, firewall blocks and SSH brute-force attempts.

| Lab | What I built | Highlights |
|---|---|---|
| [Lab 01](lab01/README.md) | Ran **two AI agents in parallel** (Claude as *alpha*, Gemini as *beta*) in a herdr multiplexer, coordinated through a file-based `mailbox/` hand-off | `alpha/web_probes.py` finds the top probing IPs in `access.log`; `beta/blocked_ports.py` analyzes `firewall.log`; `beta/make_report.py` merges both. All `check.py` validations **PASS** |
| [Lab 02 A](lab02/partA/README.md) | A **ReAct tool-calling agent** in Python (`agent/`): OpenAI-compatible client, a gated `run_shell` tool, JSON-schema-validated answers, transcripts | Found the top SSH brute-force source in `auth.log`; 17/17 checks passed |
| [Lab 02 B](lab02/partB/README.md) | **Context management** for the agent: clipping long tool output and a sliding window over old tool results | Cut input tokens from **31,192 to 7,528 (−76%)** with the same answers |

## Repository layout
```
agent/        my tool-calling agent (client, loop, tools, prompts)
lab01/        plan, task briefs, agent outputs, mailbox hand-off messages
lab02/partA/  agent build, rules run, transcripts
lab02/partB/  clip + window changes, before/after transcripts
```

## Run it
```bash
python3 -m venv .venv && source .venv/bin/activate
export SRT521_API_BASE=...  SRT521_API_KEY=...  SRT521_MODEL=...
python3 -m agent "Which source IP had the most failed SSH password attempts?" \
  --data lab02/partA/data --tools run_shell --transcript out.json
```

**Skills:** Python · log analysis · LLM agents and tool calling · prompt and context engineering · Linux/WSL · tmux · Git
