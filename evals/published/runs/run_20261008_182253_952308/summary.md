# Evaluation Run run_20261008_182253_952308

**Evaluation**: Paired quality and integrity evaluation  
**Capability**: literature-review-integrity  
**Model**: claude  
**Timestamp**: 2026-10-08T18:22:53.952697Z  
**Target commit**: 58028238e8594de9c5219cbf3fd8a6b19c2e2fd6 (clean)  
**Engine**: 1.0.0 (artifact_scoring=1.0.0, citation=1.0.0, claims=1.0.0, prisma=1.0.0)  
**Resolved model**: claude-opus-5-5[1m]  
**Cases**: 16  
**Final integrity statuses**: valid=10, valid_with_warnings=3, invalid=3

Quality and integrity are separate measurements. The integrity status does not imply that the quality score passed a quality threshold.

| Case | First-pass quality | First-pass integrity | Final quality | Final integrity | Validated artifact (SHA-256) |
|---|---:|---:|---:|---:|---|
| integrity-case-001 | 40.5 | 71.4 (invalid) | 48.5 | 100.0 (valid) | [artifacts/integrity-case-001.json](artifacts/integrity-case-001.json) `ba9e94ba9a96832e71c765f206d0f6d770c08ab676302579659ca140403e8330` |
| integrity-case-002 | 30.5 | 71.4 (invalid) | 41.5 | 100.0 (valid) | [artifacts/integrity-case-002.json](artifacts/integrity-case-002.json) `fceb58e52ad0e7e586387892ad5f14b4ceae8c98b9cd95ad5232b9307900f066` |
| integrity-case-003 | 61.9 | 71.4 (invalid) | 47.8 | 100.0 (valid) | [artifacts/integrity-case-003.json](artifacts/integrity-case-003.json) `605340a7e4708c06271a1d50b4fdae3240cd283e4d4a0b74fa8f406e08efabb1` |
| integrity-case-004 | 33.6 | 85.7 (invalid) | 39.5 | 100.0 (valid) | [artifacts/integrity-case-004.json](artifacts/integrity-case-004.json) `79307fb58010dc8ed6b533ad27771e4b6a9bdbfce7c7435eec36d1a45771ea77` |
| integrity-case-005 | 42.5 | 65.6 (invalid) | 58.4 | 87.5 (valid_with_warnings) | [artifacts/integrity-case-005.json](artifacts/integrity-case-005.json) `09d6f17fe7b95c51b01467859201044c798754309f89333ca13b9345f9ee4f06` |
| integrity-case-006 | 30.5 | 75.0 (invalid) | 46.4 | 100.0 (valid) | [artifacts/integrity-case-006.json](artifacts/integrity-case-006.json) `b6dd4da79786819b3da8757ae3f91a7ed4c84f7cfcb796e0ed66948fd0a3c936` |
| integrity-case-007 | 21.0 | 91.7 (invalid) | 19.6 | 100.0 (valid) | [artifacts/integrity-case-007.json](artifacts/integrity-case-007.json) `c39d09501f2cd7effbd46be97176341314f91b41b374eea9cc6a2cefdb06a36c` |
| integrity-case-008 | 36.4 | 91.7 (invalid) | 31.0 | 100.0 (valid) | [artifacts/integrity-case-008.json](artifacts/integrity-case-008.json) `a0377b6b2ba88081653f17cf7961fa4cfbae33dc4faf8b6b1b0e591b070bae98` |
| integrity-case-009 | 27.0 | 91.7 (invalid) | 25.5 | 100.0 (valid) | [artifacts/integrity-case-009.json](artifacts/integrity-case-009.json) `a4a514f1bf9ff530f2e549523ca2378f6ca9238d700baa5ea0e606749dfab620` |
| integrity-case-010 | N/A | N/A | N/A | N/A (invalid) | [artifacts/integrity-case-010.json](artifacts/integrity-case-010.json) `78d86be2b16d877ac4978ae3f6e8178ebdf739b0dae31e69bd55b6ecd727e424` |
| integrity-case-011 | 46.5 | 10.0 (invalid) | 41.8 | 100.0 (valid) | [artifacts/integrity-case-011.json](artifacts/integrity-case-011.json) `afaf99edcc44a8a50f76b7669f7ff93d1d767b23e499d8dffb6ddf8e049e9e40` |
| integrity-case-012 | N/A | N/A | N/A | N/A (invalid) | [artifacts/integrity-case-012.json](artifacts/integrity-case-012.json) `b7270e30dd9f7c53aae171314df08964fc3b6560f818aff2388d32ca025d2b06` |
| integrity-case-013 | N/A | N/A | N/A | N/A (invalid) | [artifacts/integrity-case-013.json](artifacts/integrity-case-013.json) `42bb1246aae2c9449b168ea7fd83bf17f88a8221cd15bd84621e27ccea42376d` |
| integrity-case-014 | 30.5 | 100.0 (valid) | 30.5 | 100.0 (valid) | [artifacts/integrity-case-014.json](artifacts/integrity-case-014.json) `6acbf6c2de4ac695f4ad05d676cc6d2e3d7577d69eebce3189772cbbd79b47b2` |
| synthetic-invalid-number | 29.7 | 30.0 (invalid) | 70.7 | 90.0 (valid_with_warnings) | [artifacts/synthetic-invalid-number.json](artifacts/synthetic-invalid-number.json) `03a5f5a56ca2bbb34afa74659d9d196945676788c5d3ffb8b3eaa055ea7351d5` |
| synthetic-valid | 81.4 | 51.9 (invalid) | 78.3 | 90.0 (valid_with_warnings) | [artifacts/synthetic-valid.json](artifacts/synthetic-valid.json) `e7a2952196d3c0e335d5b4d2d2a26d14e8cfe804f41e3a5916a532f46b884a97` |
