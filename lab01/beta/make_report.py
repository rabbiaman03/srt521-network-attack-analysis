import json

def main():
    with open("alpha/output.json", "r", encoding="utf-8") as f:
        alpha_data = json.load(f)

    with open("beta/blocked.json", "r", encoding="utf-8") as f:
        beta_data = json.load(f)

    beta_sources_set = set(beta_data.get("sources", []))

    block = []
    already_blocked = []

    for entry in alpha_data.get("top", []):
        ip = entry["ip"]
        if ip in beta_sources_set:
            already_blocked.append(ip)
        else:
            block.append(ip)

    ports = beta_data.get("ports", [])
    top_port = ports[0]["port"] if ports else None

    report = {
        "block": block,
        "already_blocked": already_blocked,
        "top_port": top_port
    }

    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
