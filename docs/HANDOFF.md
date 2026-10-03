# Handoff: history, decisions and open work

For a new team member (Claude Code joins the Mac side on 3 Oct 2026). It is deliberately short; the full record lives in the shared project tracker (HTML and Markdown, kept outside this repository) and in the commit messages.

## History in brief

| When | Version, commit | What happened |
|---|---|---|
| Sept 2026 | PointTruth to PFU | Exact-arithmetic point-file converter (browser and CLI) built with a Windows partner. One native Civil 3D 2027 round trip (international feet to metres, PENZD) came back byte-identical. |
| 27 Sep | public snapshot `87a202a` | Published as a fresh public history (option B). The private history and evidence stay private. MIT licence, copyright freyjay. |
| 28 Sep–1 Oct | 3.3.6 to 3.3.7 | Owner's palette and theme, start page, wording ("Arithmetic and preservation checks passed", naming the declared unit), readiness line, declaration summary with the exact factor, before/after example, unit clues (three levels), control-point line, 8-decimal default, optional unit-reference help. The Windows review of `ff68746` found F1–F5 and S1–S7, all fixed in 3.3.7 (`d4ef080`). |
| 2 Oct | 3.3.8 `3b4dd23` | PFU-01 / N1: the run stays active through verification and publication ("Verifying…"). Windows confirmed N1 fixed, but found R338-01 and R338-02. |
| 3 Oct | 3.3.9 | R338-01: every interruption path retires the run through one `abandonRun()` (the page can no longer stay stuck busy). R338-02: a new run clears the previous output and downloads first. Checks G45–G47, verified as negative controls against 3.3.8. **Awaiting Windows review.** |

Each release had the core gate twice (identical archives, VERIFIED), the browser suite, the owner's macOS core gate, and CI 6/6. The engine and the CLI differ between releases only by the version string.

## Key decisions

**By the owner:**

- **Full-project scope:** corridors, pipes, labels and references are required. The point-file tool is a component, not completion.
- **Wording:** "Arithmetic and preservation checks passed" plus "Please make sure the source file is really in ⟨unit⟩."
- **Defaults and interface:** 8 decimals by default (a handoff keeps its own); unchosen unit fields highlighted; **no greying of decimal choices** (an earlier misunderstanding, withdrawn); the source unit reference is optional, with help.
- **File names are never unit clues.**
- **Support claim:** Chrome, Safari, Edge and Brave on desktop; no phone support yet; no Linux mentions in user-facing text.
- **Versioning:** a bug-fix round is a patch version (3.3.x).

**With the Windows reviewer:**

- one implementation line;
- evidence labelled by who ran it;
- the shared tracker is the progress record;
- the inventory-first DWG direction.

## Working conventions

- **Changes travel as commits on GitHub `master`.** Reviews come back as packages with probes, which we run unchanged.
- **Every reply states the exact commit**, the gate results, and what was *not* run.
- **The owner pushes, or approves the push.**
- **The owner hand-tests installed browsers** with the hands-on checklist, because the Windows reviewer's browser policy blocks local pages.

## Open work (as of 3.3.9)

1. **The Windows review of 3.3.9**, then mark PFU-01 closed or reopen it. Their `probe_lifecycle_edges.cjs` needs Node 24 or later; it fails during setup on Node 22.
2. **Point-file acceptance:**
   - installed browsers on the current build (the owner, by hand);
   - the four Civil 3D cases (U.S. survey feet to metres, metres to international feet, PNEZD, a browser-produced download);
   - capacity up to 64 MiB on representative hardware;
   - broader accessibility;
   - Intel Mac.
3. **The DWG direction (the next real feature).** Return the DWG response:
   - **correct three roadmap assumptions:** `INSUNITS=21` supports U.S. survey feet since AutoCAD 2017; LandXML alone cannot prove a whole project survived; commercial engines (for example an ODA Civil SDK) are unevaluated, not incapable;
   - **answer the reviewer's 14 design questions** (API coverage, live references, detecting omitted objects, corridors and pipe catalogs, labels, "same design" tolerances, the Civil 3D 2027 seat, when to evaluate ODA);
   - **draft the read-only project inventory data contract v0.1**: a schema, synthetic fixture projects and a portable report viewer. The native collector inside Civil 3D is the Windows side's.
4. **Evidence housekeeping:** keep the CI artifacts before they expire; send the owner's Mac run folders if an audit is wanted.
