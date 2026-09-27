# Payload identity: format `unit-converter-payload/1`

This is the identity of the **files inside** a canonical tested candidate, independent of the ZIP container. It sits beside two other identities, and none of the three is inferred from the others:

| Statement | Established by |
|---|---|
| Which files were packaged | payload identity (this document) |
| Which exact bytes were tested | the archive SHA-256 in the candidate and run records |
| Which tests passed, where | each platform's own run record |

## Definition

1. **Validate every entry**, in the archive's own order. Check the original decoded ZIP spelling (`ZipInfo.orig_filename`) before accepting `filename`, which Python can truncate at NUL or rewrite on Windows; reject any reader-altered spelling. Reject: a duplicate name; names that collide under Unicode case folding; an invalid path (empty, absolute, containing `\` or NUL, a drive prefix such as `c:`, or an empty, `.` or `..` segment; a trailing `/`); a directory entry or anything other than a regular file (the file-type bits must be regular or unset). Paths are kept exactly as spelled: never normalized, never rewritten.
2. **Declared mode** comes from rule `unit-converter-mode-rule/1`: a path matching `*.sh` **case-sensitively** is `100755`; every other file is `100644`. The rule is independent of the host: no case folding, and no reading of filesystem permission bits.
3. **Canonical candidates** (`check_modes=True`, always used by the release builder): the entry's **actual stored mode must equal the declared mode**, otherwise the candidate is refused. For archives from other writers, `check_modes=False` may be used. The result is then explicitly a *declared-mode* identity (`modes_checked: false`), and it says nothing about the stored permissions.
4. **Read each entry by its ZIP record**, never by name, so a hidden duplicate can never be read twice.
5. **Encoding:** a UTF-8 JSON object `{"files": [...], "format": "unit-converter-payload/1", "mode_rule": "unit-converter-mode-rule/1"}`. Each file is `{"mode": "<6 octal digits>", "path": <exact path>, "sha256": <lowercase hex>, "size": <bytes>}`. Files are sorted by the UTF-8 bytes of `path`. Keys are sorted; the separators are `,` and `:` with no spaces; non-ASCII characters are kept as UTF-8; there is **no BOM and no final newline**.
6. **Digest** = SHA-256 of those exact bytes.
7. **Included:** every packaged file, including the regenerated `PACKAGE-CONTENTS.sha256`. The identity itself lives only in the external records, so it never refers to itself.

The pinned reference example is in `tests/test_payload_identity.py`: two files, with the expected encoding and digest `a5b3383e…`.

## Records and comparison

- Candidate record: `payload_identity = {format, mode_rule, digest, members, modes_checked}`. Run record: `tested_payload_identity`, the same object. This is an additive field; record schema `/2` is unchanged.
- `scripts/compare_runs.py` validates passing core records, supported identity format and mode rule, complete digest/member fields, strict mode checking, and the same clean recorded commit. By default it also reads each adjacent `tested-partial.zip`, verifies its SHA-256 and recomputes its strict payload identity. Missing or mismatching artifacts fail. `--records-only` explicitly compares claims without inspecting archives and labels artifacts **NOT CHECKED**; its exit status is not artifact acceptance. Missing or unsupported identities are **unavailable, never a match**. Neither mode authenticates who executed the reported tests.

## What byte identity is claimed for

The candidate archive's bytes are expected to be identical **across the measured runtime matrix**, and are verified there by comparing records. They are **not** promised for every future ZIP writer or Python implementation. Measured so far, on the proposal before this contract: Linux (Python 3.12.3, zlib 1.3) and Windows 10 (Python 3.13.7, zlib 1.3.1), both producing `5439a084…`. The committed revision containing this contract must be re-measured on Linux, macOS and Windows.

## Scope limits

- The builder produces and validates canonical candidates. For arbitrary received archives, this implementation performs the structural checks above; with `check_modes=False` it does not verify permissions.
- It is a packaging identity. It says nothing about units, column mapping or CAD acceptance.
