# Topics Reference

Topics are research areas automatically assigned to works. Topics exist in a
four-level hierarchy: domain > field > subfield > topic.

## Top-level

| Field                                    | Sort | Group_by | Filter |
| ---------------------------------------- | :--: | :------: | :----: |
| `cited_by_count`                         |   ✓  |    ✓     |    ✓   |
| `display_name`                           |   ✓  |          |    ✓   |
| `from_created_date`                      |   ✓  |          |    ✓   |
| `id`                                     |   ✓  |    ✓     |    ✓   |
| `openalex`                               |   ✓  |    ✓     |    ✓   |
| `works_count`                            |   ✓  |    ✓     |    ✓   |

## Hierarchy

| Field         | Sort | Group_by | Filter |
| ------------- | :--: | :------: | :----: |
| `domain.id`   |   ✓  |    ✓     |    ✓   |
| `field.id`    |   ✓  |    ✓     |    ✓   |
| `subfield.id` |   ✓  |    ✓     |    ✓   |

## Ids

| Field          | Sort | Group_by | Filter |
| -------------- | :--: | :------: | :----: |
| `ids.openalex` |   ✓  |    ✓     |    ✓   |

## Narrowing a works search by topic (worked example)

Raw `--search` on works pulls topical noise — a query like
`LLM agent governance oversight safety` returns off-topic gen-AI papers
(HR, education, medicine) ranked high. Filter by a resolved topic instead of
relying on keywords alone.

**Step 1 — resolve the topic id** (re-run for your own subject; ids change):
```bash
uv run scripts/openalex_cli.py filter topics \
  --search "large language models" \
  --select "id,display_name,works_count" --per-page 5
# e.g. https://openalex.org/T13910 — "Computational and Text Analysis Methods"
```

**Step 2 — filter works by that topic, rank within it:**
```bash
uv run scripts/openalex_cli.py filter works \
  --filter "topics.id:T13910,publication_year:>2022,type:article" \
  --search "agent governance oversight" \
  --sort "cited_by_count:desc" \
  --select "id,doi,title,publication_year,cited_by_count" --per-page 10
```

`topics.id` (single best-matching topic) narrows hardest; use `primary_topic.id`
for the work's main topic only, or a broad `concepts.id:C…` when no single topic
fits. `--search` then ranks *within* the filtered slice rather than across all
of OpenAlex. The stderr line reports total hits so you can judge whether the
filter is too tight or too loose.
