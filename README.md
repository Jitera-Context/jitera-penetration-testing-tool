# Jitera

AI penetration testing for your apps. Autonomous AI agents test your code and running applications the way an attacker would, and back each finding with a working proof of concept.

Jitera is built on [Strix](https://github.com/usestrix/strix) (Apache-2.0). It adds our brand and network identity, and turns off the upstream vendor's cloud services and telemetry. See [What's different from Strix](#whats-different-from-strix).

## What it does

- **Full pentesting toolkit** inside a Docker sandbox: HTTP interception proxy (Caido), browser automation, shell, Python exploit runtime, reconnaissance, static and dynamic analysis.
- **A team of agents**: specialised agents for recon, exploitation and validation work in parallel and share what they find.
- **Validated findings**: each comes with a proof of concept, a CVSS score and fix guidance.
- **Reports** in Markdown, PDF, JSON and SARIF.

It covers the OWASP Top 10 and beyond: access control and IDOR, injection, SSRF, XXE and RCE, XSS and CSRF, business logic and race conditions, authentication and sessions, cloud misconfiguration, and API security.

Only test systems you are authorized to test.

## Requirements

- Docker, running
- Python 3.12+ and a recent [uv](https://docs.astral.sh/uv/). Older uv versions rewrite `uv.lock`, so always pass `--frozen`.
- Go 1.24+ for the interactive terminal UI. Headless mode (`-n`) works without it.
- An LLM: an API key for any [LiteLLM](https://docs.litellm.ai/docs/providers) provider, or a ChatGPT subscription

## Install

```bash
git clone git@github.com:Jitera-Context/jitera-penetration-testing-tool.git
cd jitera-penetration-testing-tool
uv sync --frozen
source .venv/bin/activate
jitera about
```

Prebuilt binaries will be published on this repository's releases once the release pipeline is in place.

## Quick start

```bash
export JITERA_LLM="openrouter/z-ai/glm-5.3"   # any LiteLLM model id
export LLM_API_KEY="your-api-key"

jitera --target https://your-app.com
```

Use `jitera`, not `strix`. The `strix` command is still installed, but it runs upstream's branding and telemetry.

## Usage

```bash
# Local code, a GitHub repository, or a live app
jitera --target ./app-directory
jitera --target https://github.com/org/repo
jitera --target https://your-app.com

# An API contract plus the live base URL
jitera --target ./openapi.yaml --target https://api.your-app.com

# Authenticated (grey-box) testing
jitera --target https://your-app.com --instruction "Log in as user:pass before testing"

# Several targets, or a file of targets
jitera -t https://github.com/org/app -t https://your-app.com
jitera --target-list ./targets.txt

# Headless, for CI and servers: quick scan, capped spend, fail on high or worse
jitera -n --target ./ --scan-mode quick --max-budget 10 --fail-on high
```

Scan modes are `quick`, `standard` and `deep` (the default). In headless mode the exit code is `0` when no findings were reported, `1` on a fatal error, and `2` when findings were reported (with `--fail-on`, only findings at or above that severity count).

### Results

Each scan writes to `strix_runs/<run-name>/`:

| File | Contents |
|---|---|
| `penetration_test_report.md` | The full report |
| `vulnerabilities/*.md` | One file per finding |
| `vulnerabilities.json` | All findings, machine-readable |
| `findings.sarif` | SARIF 2.1.0 for code-scanning tools |
| `run.json` | Status, timing and LLM cost |

Open them in the local viewer:

```bash
jitera view                 # most recent run
jitera view my-run-name     # a specific run
```

### Other commands

```bash
jitera about                    # version and attribution
jitera auth login chatgpt       # run on a ChatGPT subscription instead of an API key
jitera --resume my-run-name     # continue a stopped scan
jitera completions zsh          # shell completion (bash and fish too)
```

## Configuration

Every upstream `STRIX_*` setting works. You can also write it as `JITERA_*`, and the `jitera` command copies it to the `STRIX_*` name.

| Variable | Purpose |
|---|---|
| `JITERA_LLM` | Model id, for example `openrouter/z-ai/glm-5.3` |
| `LLM_API_KEY` | API key for that provider |
| `LLM_API_BASE` | Base URL for a local model (Ollama, LM Studio) |
| `PERPLEXITY_API_KEY` or `EXA_API_KEY` | Optional web search for the agents |
| `JITERA_IMAGE` | Sandbox image. Default: upstream's `ghcr.io/usestrix/strix-sandbox:1.4.1` |

Settings are saved in `~/.strix/cli-config.json`. To give the agents extra tools, list MCP servers in `~/.strix/mcp-servers.json`. The [upstream documentation](https://docs.strix.ai/) describes every option.

## What's different from Strix

| | Strix | Jitera |
|---|---|---|
| Command | `strix` | `jitera` |
| User-Agent of our own calls | `python-requests/…` | `Jitera/<version> (+https://jitera.com)` |
| User-Agent of scan traffic | A generic Chrome browser | `Mozilla/5.0 (compatible; Jitera/<version>; +https://jitera.com)` on proxy replays, the sandbox browser, and requests the agent writes |
| Telemetry | On, sent to Strix | Off by default |
| `cloud` and `--update` | Strix Cloud and self-update from Strix releases | Blocked |
| Viewer | Strix Cloud upsells, email and feedback relays | Hidden |
| CLI, terminal UI, reports, viewer | Strix | Jitera |

Customers can recognize our authorized scan traffic by its User-Agent.

## Developing

This repository is a fork kept easy to sync with upstream:

- Edit the source directly. Our own code lives in `strix/jitera/`, our tests in `tests/jitera/`.
- `fork/dev save` records every change since the upstream checkpoint (`fork/CHECKPOINT`) as patches in `fork/patches/`. Commit the code and its patches together.
- `fork/dev sync` takes a new upstream: back to the checkpoint, remove our changes, take the latest upstream, re-apply the patches.

```bash
fork/dev help       # every command
fork/dev status     # checkpoint, how far upstream moved, patches out of date
fork/dev test       # brand audit, lint, type check, tests
```

The full guide with diagrams is [`fork/architecture.html`](fork/architecture.html). In Claude Code, use `/fork-change` and `/fork-sync`.

## License

Apache-2.0. Built on [Strix](https://github.com/usestrix/strix) by the Strix authors. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
