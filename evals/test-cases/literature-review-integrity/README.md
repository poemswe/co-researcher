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

All fixtures and prompts in this directory are synthetic. Runtime-only case
collections can be loaded by passing their containing directory to
`load_cases()`; the adapter has no built-in path to a private collection.
