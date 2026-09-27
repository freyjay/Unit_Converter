Records produced against PFU 3.3.5 with the round-9 runner (pfu-capacity-record/1). Superseded by the 3.3.6 records one
directory up, but retained as evidence. Known defects of that runner (partner review F11-02): `save_handoff.seconds` in the
64 MiB records is cumulative from source selection (load + convert + output download + save), not save-only; the 16 MiB record
was produced by an earlier revision of the runner with a correctly reset timer, which is why its ordering differs; manifest
identity was hashed but not compared; a reopened-page crash was recorded under the producer's flag. The 64 MiB producer-open
FAILED outcome is real: the reopen navigation crashed the renderer. Its cause is labelled as captured manually below rather
than asserted by the runner.
