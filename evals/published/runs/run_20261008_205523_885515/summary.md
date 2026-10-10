# Evaluation Run run_20261008_205523_885515

**Evaluation**: Paired quality and integrity evaluation  
**Capability**: literature-review-integrity  
**Model**: codex  
**Timestamp**: 2026-10-08T20:55:23.885823Z  
**Target commit**: 58028238e8594de9c5219cbf3fd8a6b19c2e2fd6 (clean)  
**Engine**: 1.0.0 (artifact_scoring=1.0.0, citation=1.0.0, claims=1.0.0, prisma=1.0.0)  
**Resolved model**: gpt-6-astra  
**Resumed from**: run_20261008_182233_844861  
**Cases**: 16  
**Final integrity statuses**: valid=10, valid_with_warnings=3, invalid=3

Quality and integrity are separate measurements. The integrity status does not imply that the quality score passed a quality threshold.

| Case | First-pass quality | First-pass integrity | Final quality | Final integrity | Validated artifact (SHA-256) |
|---|---:|---:|---:|---:|---|
| integrity-case-001 | 53.5 | 71.4 (invalid) | 53.5 | 100.0 (valid) | [artifacts/integrity-case-001.json](artifacts/integrity-case-001.json) `8d8229e4a4665a9b2f90fd855fa77b5d9e21f5043a2843b9e39143e99776ffd2` |
| integrity-case-002 | 47.5 | 71.4 (invalid) | 55.0 | 100.0 (valid) | [artifacts/integrity-case-002.json](artifacts/integrity-case-002.json) `f49c8b77176b572a966964d8ef62bfd0a62620fa66276ddb43b6e4a4168b5d95` |
| integrity-case-003 | 54.0 | 71.4 (invalid) | 49.5 | 100.0 (valid) | [artifacts/integrity-case-003.json](artifacts/integrity-case-003.json) `99a99d81291bb36a3429525d096161fec2538edcbd2ce75065158debf1f36e54` |
| integrity-case-004 | 47.5 | 85.7 (invalid) | 51.5 | 100.0 (valid) | [artifacts/integrity-case-004.json](artifacts/integrity-case-004.json) `f2fe5195cbfe3db3317106396b41b87702ae82c2830d842583da61f5220d7ac0` |
| integrity-case-005 | 31.0 | 65.6 (invalid) | 45.5 | 87.5 (valid_with_warnings) | [artifacts/integrity-case-005.json](artifacts/integrity-case-005.json) `6c1cfca1f584721a620b3c365ed8fc3035a77f98aeb7a3e13c469093ce7f963f` |
| integrity-case-006 | 52.0 | 75.0 (invalid) | 53.0 | 100.0 (valid) | [artifacts/integrity-case-006.json](artifacts/integrity-case-006.json) `2b266812e4273cdf7f086cbd5764785fc8c39ea180608c3837791ab6aa84d671` |
| integrity-case-007 | 53.0 | 91.7 (invalid) | 49.5 | 100.0 (valid) | [artifacts/integrity-case-007.json](artifacts/integrity-case-007.json) `4ba9a79b6a3eee222344b3add92472dd42e2ca3c230a53498d904a6bf623e62a` |
| integrity-case-008 | 59.0 | 91.7 (invalid) | 59.5 | 100.0 (valid) | [artifacts/integrity-case-008.json](artifacts/integrity-case-008.json) `6ff5644f76491d5602fa5297d24b56f44eefb69654cbfdb202f08c5a848cf709` |
| integrity-case-009 | 58.5 | 91.7 (invalid) | 51.5 | 100.0 (valid) | [artifacts/integrity-case-009.json](artifacts/integrity-case-009.json) `ed60c549fa459b8f4927bad0ceaa2b3ff01c5930c78b257d371d69e0da7b06c3` |
| integrity-case-010 | N/A | N/A | N/A | N/A (invalid) | [artifacts/integrity-case-010.json](artifacts/integrity-case-010.json) `31f104b0764b2e15da246a560550a32d7571e9478d5186ff1ed1fcf7adb99c57` |
| integrity-case-011 | 59.0 | 10.0 (invalid) | 54.0 | 100.0 (valid) | [artifacts/integrity-case-011.json](artifacts/integrity-case-011.json) `d11381fa64867977b10a1bfe188eedd697960984ce381fcfcbce752c2013d476` |
| integrity-case-012 | N/A | N/A | N/A | N/A (invalid) | [artifacts/integrity-case-012.json](artifacts/integrity-case-012.json) `a8cf900301c93d4deac4bdc747e684c2823aa98cb65d2ea72d24e3ac8ed691ed` |
| integrity-case-013 | N/A | N/A | N/A | N/A (invalid) | [artifacts/integrity-case-013.json](artifacts/integrity-case-013.json) `f7115e256a4096421ffba6b113c36562eab55018e3f6f97ff71cff60d1fc5109` |
| integrity-case-014 | 52.5 | 100.0 (valid) | 52.5 | 100.0 (valid) | [artifacts/integrity-case-014.json](artifacts/integrity-case-014.json) `7ef979ea4653916c2cdc9f813e73b4bde00a6bf35149a202377d0939f2ff9d1c` |
| synthetic-invalid-number | 74.2 | 56.7 (invalid) | 68.8 | 90.0 (valid_with_warnings) | [artifacts/synthetic-invalid-number.json](artifacts/synthetic-invalid-number.json) `5462e7ec06dfdb36cfe41927a5699bd4d9e199e37778e6fb726389da8d0af2c9` |
| synthetic-valid | 85.9 | 90.0 (valid_with_warnings) | 85.9 | 90.0 (valid_with_warnings) | [artifacts/synthetic-valid.json](artifacts/synthetic-valid.json) `e49f13bb9c9786cd0af2d7673b9848bb4b5b0b07915aaadd84536c51ea481279` |
