# Literature-review integrity evaluation

This capability evaluates a model-produced literature-review workspace twice:
the immutable first pass and the bounded-repair system result. Research quality
and deterministic integrity are reported independently.

Each case directory contains public `case.json` input and a scorer-only
`expected.json` outcome. The runner reads the outcome only after generation,
validation, repair, and quality judging have finished. Neither file is copied
into the temporary workspace.

All fixtures and prompts in this directory are synthetic. Runtime-only case
collections can be loaded by passing their containing directory to
`load_cases()`; the adapter has no built-in path to a private collection.

