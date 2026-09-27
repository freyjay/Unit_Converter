# Documents: what is current

**Current** — read these, in this order:

1. [`CURRENT-STATUS.md`](CURRENT-STATUS.md): what is verified, on which platforms, and what is still open (latest section first).
2. [`PROVENANCE.json`](PROVENANCE.json): exact identities of the app and the converter, and what changed from the Civil 3D-tested build.
3. [`FEATURE-INVENTORY.md`](FEATURE-INVENTORY.md): every capability, its status, and scope decisions.
4. [`TEST-GATE-MAP.md`](TEST-GATE-MAP.md): how the checks fit together and what each one proves.
5. [`EXPOSURE-INVENTORY.md`](EXPOSURE-INVENTORY.md): personal data in tracked files (usernames masked), plus binary files still needing a human look; regenerate it with `scripts/scan_exposure.py`.
6. [`EVIDENCE-ARCHIVES.json`](EVIDENCE-ARCHIVES.json): every tested archive (in this repository or kept elsewhere) with its SHA-256 and where it is retained; archives are evidence, never inputs to a new tested candidate.
7. [`PAYLOAD-IDENTITY.md`](PAYLOAD-IDENTITY.md): the payload identity of tested candidates (`unit-converter-payload/1`), and how runs on different machines are compared (`scripts/compare_runs.py`).
8. [`WINDOWS-TEST-RUNSHEET.md`](WINDOWS-TEST-RUNSHEET.md) and the procedures under [`../acceptance/`](../acceptance/): hands-on tests.

**Evidence and history** are kept in the owner's private repository: earlier ledgers, review responses and correspondence, raw run folders from Linux, macOS and Windows, screenshots and Civil 3D operator logs. [`PUBLIC-EVIDENCE-MAP.json`](PUBLIC-EVIDENCE-MAP.json) lists every omitted file with its original SHA-256 and what was done with it. [`PUBLIC-PROFILE.json`](PUBLIC-PROFILE.json) declares the private areas; the release builder refuses a public tree that contains any of them.
