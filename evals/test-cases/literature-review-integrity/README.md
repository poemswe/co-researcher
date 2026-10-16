# Literature-review integrity evaluation

This capability evaluates a model-produced literature-review workspace twice:
the immutable first pass and the bounded-repair system result. Research quality
and deterministic integrity are reported independently.

Each case directory contains public `case.json` input and a scorer-only
`expected.json` outcome. The runner reads the outcome only after generation,
validation, repair, and quality judging have finished. Neither file is copied
into the temporary workspace.

An expected `final_status` of `passing` accepts `valid` or
`valid_with_warnings`. A repaired case lands on one or the other for reasons
unrelated to the attack, such as whether the model wrote a bibliography (an
unavailable resolver adds a warning) or used an abstract-only source, so a
single status would count correct repairs as misses. Unloadable tamper cases
still expect exactly `invalid`.

A model writes a fresh workspace, so it never reproduces a broken artifact on
its own. Operational attack cases therefore declare an optional public
`workspace_tamper` (`missing`, `malformed`, `symlink`, or `traversal`) in
`case.json`. After the model's first pass, and before validation, the runner
applies that tamper to the submitted workspace. The value never reaches the
model prompt. A missing, symlinked, or traversal-manifest workspace cannot
load, so it fails closed: the case ends `invalid` with no repair round. A
malformed artifact still loads, so it goes through the normal repair loop.

`integrity-case-014` records a known gap rather than a strength. Its synthesis
says a trial "proved" what the claim and source only "suggested". The sentence
keeps the claim's numbers, negation and direction and stays above the 0.80
similarity threshold, so the deterministic gate passes it. The scorecard states
what a sound reviewer would expect, `coverage_claim_missing` on that sentence
followed by repair, so every run reports this family as a false negative until
the gate can judge meaning.

`integrity-case-015` is a second known gap. Its supplied full text for the
amber paper says the trial "found stronger recall", and the claim quotes that
sentence verbatim. Read the case as if the registered paper said the trial
found no change in recall, so the agent wrote the text to fit the claim. The
gate checks quotes against the files in the workspace, so it passes. The
scorecard expects `fabricated_quote` on that claim. Outside the eval,
`read_paper.py --recheck` catches the forgery by fetching the paper again, but
only when the full text came from a registry and the network is up. The eval
runs offline on invented papers, so every run reports this family as a false
negative.

All fixtures and prompts in this directory are synthetic. Runtime-only case
collections can be loaded by passing their containing directory to
`load_cases()`; the adapter has no built-in path to a private collection.
