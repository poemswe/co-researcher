# Evaluation Run run_20261008_155105_866156

**Evaluation**: Paired quality and integrity evaluation  
**Capability**: literature-review-integrity  
**Model**: codex  
**Timestamp**: 2026-10-08T15:51:05.866498Z  
**Target commit**: 154c26fe2887d76845a89673f2431e5c76274423 (clean)  
**Engine**: 1.0.0 (artifact_scoring=1.0.0, citation=1.0.0, claims=1.0.0, prisma=1.0.0)  
**Resolved model**: gpt-6-astra  
**Resumed from**: run_20261008_153627_188499  
**Cases**: 15  
**Final integrity statuses**: valid=9, valid_with_warnings=3, invalid=3

Quality and integrity are separate measurements. The integrity status does not imply that the quality score passed a quality threshold.

| Case | First-pass quality | First-pass integrity | Final quality | Final integrity | Validated artifact (SHA-256) |
|---|---:|---:|---:|---:|---|
| integrity-case-001 | 53.5 | 71.4 (invalid) | 47.0 | 100.0 (valid) | [artifacts/integrity-case-001.json](artifacts/integrity-case-001.json) `5e79c4b20d1994be8a94513031019eed30ed6554ce5cea02c159cd7bfb6fd98c` |
| integrity-case-002 | 48.0 | 71.4 (invalid) | 61.5 | 100.0 (valid) | [artifacts/integrity-case-002.json](artifacts/integrity-case-002.json) `bf23b6c1d5be5c5b971ea8cdab97902375abdd1f62c41e6f28e4375b3f768ab8` |
| integrity-case-003 | 53.5 | 71.4 (invalid) | 53.5 | 100.0 (valid) | [artifacts/integrity-case-003.json](artifacts/integrity-case-003.json) `1453f5de2a81f39fe27bf74c7fb2b747941bfb49e0326de73b1a72bb8fb6155e` |
| integrity-case-004 | 41.0 | 85.7 (invalid) | 45.0 | 100.0 (valid) | [artifacts/integrity-case-004.json](artifacts/integrity-case-004.json) `3b9d63253f84c3c3c9337dabefc932ffac4cdd5c769a18e5a6c66016722aa9a8` |
| integrity-case-005 | 34.5 | 65.6 (invalid) | 31.5 | 87.5 (valid_with_warnings) | [artifacts/integrity-case-005.json](artifacts/integrity-case-005.json) `da82e5f3b9b9a499dd4b10d27e523c9faf07a6a9e20d1d69e5c2f728526a2051` |
| integrity-case-006 | 55.5 | 75.0 (invalid) | 49.5 | 100.0 (valid) | [artifacts/integrity-case-006.json](artifacts/integrity-case-006.json) `f5c7d31ccd735e24302c9d5cb672c13ea4b0cca5fcf2effdf45de28a48068eab` |
| integrity-case-007 | 49.0 | 91.7 (invalid) | 41.5 | 100.0 (valid) | [artifacts/integrity-case-007.json](artifacts/integrity-case-007.json) `bcc05398f12e5d2441c3f695e12ebe683cb0feca36604c8908cab7b6f666dc37` |
| integrity-case-008 | 43.5 | 91.7 (invalid) | 51.5 | 100.0 (valid) | [artifacts/integrity-case-008.json](artifacts/integrity-case-008.json) `6a1283bf1ca4d71efbd784b1355af583b38dd3ebe9731de75beb4b7a91284284` |
| integrity-case-009 | 58.5 | 91.7 (invalid) | 52.5 | 100.0 (valid) | [artifacts/integrity-case-009.json](artifacts/integrity-case-009.json) `40b74d11ded8c9215200517211bec2093b3290ee6b6750eae113d65e4d5e2ed2` |
| integrity-case-010 | N/A | N/A | N/A | N/A (invalid) | [artifacts/integrity-case-010.json](artifacts/integrity-case-010.json) `ecbe34ee7e46f6a667e336d7cf0d14669f1ca15ef1e1c84e4b035e0ed2af5be1` |
| integrity-case-011 | 54.0 | 10.0 (invalid) | 54.0 | 100.0 (valid) | [artifacts/integrity-case-011.json](artifacts/integrity-case-011.json) `9a0afc7e4f8efffa5101dcab7a3360ff017fbf1484e808bf72edf719421fb2c2` |
| integrity-case-012 | N/A | N/A | N/A | N/A (invalid) | [artifacts/integrity-case-012.json](artifacts/integrity-case-012.json) `b0308ebbcce88d32019aaccfdd4618aaf8c3841056da17e34bd341147ebc663a` |
| integrity-case-013 | N/A | N/A | N/A | N/A (invalid) | [artifacts/integrity-case-013.json](artifacts/integrity-case-013.json) `6cd48e8192d964c5a923cb26a8079ee13d24111c4b84af9bb1bcc7946db437d5` |
| synthetic-invalid-number | 72.8 | 56.7 (invalid) | 79.6 | 90.0 (valid_with_warnings) | [artifacts/synthetic-invalid-number.json](artifacts/synthetic-invalid-number.json) `63033893b0eb5ec4f40c04b7d22eb95a09258e39d5026de50e18225b5815833c` |
| synthetic-valid | 84.8 | 81.2 (invalid) | 87.0 | 90.0 (valid_with_warnings) | [artifacts/synthetic-valid.json](artifacts/synthetic-valid.json) `9866d1d1454afd925ea7ff19ea893220bf38e1a1f18fb29bb3eee740f655199c` |
