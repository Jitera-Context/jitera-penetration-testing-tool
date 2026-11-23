---
name: vulnerable-components-blackbox
description: Black-box SCA -- fingerprint the client-side libraries a running app serves and report known-CVE versions with detect_vulnerable_components + create_dependency_report, no source or lockfile needed
---

# Vulnerable & Outdated Components (black-box)

Upstream's `dependency-cve-scanning` skill runs `trivy` over a repository's
lockfiles. That needs source you do not have on an external, black-box scan. Use
this skill then: the only evidence of a vulnerable component is what the running
app serves to the browser, and **known-CVE components are a first-class finding
even without a dynamic PoC** (the SCA exception to the dynamic-validation rule).

The model is unreliable at remembering which exact versions are vulnerable and
which version fixed them, so do **not** judge versions by memory. Extract the
version, then let `detect_vulnerable_components` match it deterministically.

## Procedure

1. **Collect served assets.** You already fetch these during recon:
   - the main HTML document(s),
   - every linked `<script src=...>` and stylesheet, fetched via the browser or
     `repeat_request`,
   - any source map (`*.js.map`), `/package.json`, or build manifest that is
     reachable.
2. **Fingerprint + match.** Call `detect_vulnerable_components` with the fetched
   assets as `[{"url": ..., "content": ...}, ...]`. It returns:
   - `detected` -- every library + version it could read,
   - `vulnerable` -- those whose version falls in a known-CVE range, each with
     `cve`, `advisory_cvss`, `cwe`, `fixed_version`, `advisory_url` and the
     `source_url` the version was read from.
3. **File each vulnerable hit** with `create_dependency_report`:
   - `package_ecosystem="npm"`, `installed_version` and `cve` from the result,
   - `manifest_path` = the `source_url` the version came from,
   - the proof is the served file + detected version + the published advisory;
     no exploit script is required.
4. **Do not stop at the tool's list.** It only knows a handful of common
   libraries. Also report, by hand, any component whose version you can read
   from a banner, `/package.json`, a version endpoint, or a `Server`/
   `X-Powered-By` header and can tie to a published advisory.

## Notes

- An empty `vulnerable` list is **not** proof the app is clean -- it means none
  of the fingerprinted libraries matched. Say so in coverage, don't claim the
  class is clear.
- Record coverage for this class with `record_coverage` even when you file
  nothing, so the run shows the component surface was actually assessed.
