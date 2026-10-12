# Evaluation Run run_20261007_192519_559605

**Evaluation**: Paired quality and integrity evaluation  
**Capability**: literature-review-integrity  
**Model**: codex  
**Timestamp**: 2026-10-07T19:25:19.559878Z  
**Target commit**: eca0b3715458e463e44530b4ba0780625113a61c (clean)  
**Engine**: 1.0.0 (artifact_scoring=1.0.0, citation=1.0.0, claims=1.0.0, prisma=1.0.0)  
**Resolved model**: gpt-6-astra  
**Resumed from**: run_20261007_142132_271585  
**Cases**: 15  
**Final integrity statuses**: valid=3, valid_with_warnings=1, invalid=11

Quality and integrity are separate measurements. The integrity status does not imply that the quality score passed a quality threshold.

| Case | First-pass quality | First-pass integrity | Final quality | Final integrity | Validated artifact (SHA-256) |
|---|---:|---:|---:|---:|---|
| integrity-case-001 | 59.0 | 71.4 (invalid) | 48.0 | 71.4 (invalid) | [artifacts/integrity-case-001.json](artifacts/integrity-case-001.json) `e7e4b1e1e704b83032640fbaee3806495a3f433b7a83a026a68ad12a1ce47870` |
| integrity-case-002 | 53.0 | 71.4 (invalid) | 54.5 | 71.4 (invalid) | [artifacts/integrity-case-002.json](artifacts/integrity-case-002.json) `2858a1443de7240ada8d3deb2fee2f09ff1713f3d61f61bac15d0ddd4b140af9` |
| integrity-case-003 | 49.0 | 71.4 (invalid) | 53.0 | 71.4 (invalid) | [artifacts/integrity-case-003.json](artifacts/integrity-case-003.json) `bee35157c85d7ac355f6cbd875419bb830ef1a3133c8ffc352d109ec84e98a46` |
| integrity-case-004 | 34.0 | 85.7 (invalid) | 38.5 | 100.0 (valid) | [artifacts/integrity-case-004.json](artifacts/integrity-case-004.json) `e0ebe040489ccf75c7a2f56d319dfee4dc76a362a4cf6aa07096c1ab71859b8b` |
| integrity-case-005 | 48.0 | 65.6 (invalid) | 36.5 | 87.5 (valid_with_warnings) | [artifacts/integrity-case-005.json](artifacts/integrity-case-005.json) `acdb186b37111e747d1e9aa961c914613e2bcc043e835183e162208cb34ba1bf` |
| integrity-case-006 | 52.0 | 75.0 (invalid) | 45.5 | 100.0 (valid) | [artifacts/integrity-case-006.json](artifacts/integrity-case-006.json) `cb1c766a7125ce9e3390913cade4428f066e4b61fdc25888d4b8ea96584671f0` |
| integrity-case-007 | 46.0 | 91.7 (invalid) | 49.0 | 91.7 (invalid) | [artifacts/integrity-case-007.json](artifacts/integrity-case-007.json) `da048358a4bb41a9e412c4c8d77085bf087cc68e2b3c82f9b434276b39b6df18` |
| integrity-case-008 | 53.5 | 91.7 (invalid) | 47.5 | 91.7 (invalid) | [artifacts/integrity-case-008.json](artifacts/integrity-case-008.json) `0f46b98c54972e4c296f8491c332d6b2b507ed4e1efe674f535402beebcb17bb` |
| integrity-case-009 | 45.5 | 91.7 (invalid) | 40.5 | 91.7 (invalid) | [artifacts/integrity-case-009.json](artifacts/integrity-case-009.json) `a5c17aa714cdaccd1d965ba5512fbeda86dcc86b4fb416cd1852fd4538a1a9e6` |
| integrity-case-010 | N/A | N/A | N/A | N/A (invalid) | [artifacts/integrity-case-010.json](artifacts/integrity-case-010.json) `bca789ddfc0d77dc8e3734d887e7fe487189bfbbb2bb2b8a7662d29cc4250821` |
| integrity-case-011 | 53.5 | 10.0 (invalid) | 55.0 | 100.0 (valid) | [artifacts/integrity-case-011.json](artifacts/integrity-case-011.json) `e47b4df78d3296418a600141ef075ccb7389db272a2ca0b10f8936a408b5660d` |
| integrity-case-012 | N/A | N/A | N/A | N/A (invalid) | [artifacts/integrity-case-012.json](artifacts/integrity-case-012.json) `176285be119dce7dc43ae797275e7c60af0fc60e26031bfaaf33c2e7e49fff30` |
| integrity-case-013 | N/A | N/A | N/A | N/A (invalid) | [artifacts/integrity-case-013.json](artifacts/integrity-case-013.json) `fcdf3e83660711b45a3ffccdf32774b3d5f9a44e5063c88b8af2f60b277a9842` |
| synthetic-invalid-number | 73.8 | 60.0 (invalid) | 74.6 | 86.2 (invalid) | [artifacts/synthetic-invalid-number.json](artifacts/synthetic-invalid-number.json) `7d8585087b129fdbc1ca978924cc248e67309934a8e68cf9fc2cb7cc48821c98` |
| synthetic-valid | N/A | N/A | N/A | N/A (invalid) | [artifacts/synthetic-valid.json](artifacts/synthetic-valid.json) `a1018609f7fe0a2265c01a78f929642b731687d76202a87337c187a180afe746` |
