# Evaluation Run run_20261008_015639_166787

**Evaluation**: Paired quality and integrity evaluation  
**Capability**: literature-review-integrity  
**Model**: claude:opus  
**Timestamp**: 2026-10-08T01:56:39.167306Z  
**Target commit**: 21c3777a8b35a95795e7b47aa5705ef595f34b49 (clean)  
**Engine**: 1.0.0 (artifact_scoring=1.0.0, citation=1.0.0, claims=1.0.0, prisma=1.0.0)  
**Resolved model**: claude-opus-5-5  
**Cases**: 15  
**Final integrity statuses**: valid=9, valid_with_warnings=3, invalid=3

Quality and integrity are separate measurements. The integrity status does not imply that the quality score passed a quality threshold.

| Case | First-pass quality | First-pass integrity | Final quality | Final integrity | Validated artifact (SHA-256) |
|---|---:|---:|---:|---:|---|
| integrity-case-001 | 59.3 | 71.4 (invalid) | 41.5 | 100.0 (valid) | [artifacts/integrity-case-001.json](artifacts/integrity-case-001.json) `695844888b6fae9f9898c13926f1be19d6231b400aa0aec845971fbf45fc213f` |
| integrity-case-002 | 46.5 | 71.4 (invalid) | 41.0 | 100.0 (valid) | [artifacts/integrity-case-002.json](artifacts/integrity-case-002.json) `6ff478592b5ea8ea9d294c45618cb9c477181ef22cc52a105679f7890af580ab` |
| integrity-case-003 | 69.3 | 71.4 (invalid) | 52.0 | 100.0 (valid) | [artifacts/integrity-case-003.json](artifacts/integrity-case-003.json) `ce77ac6376386f5dd8a4ab0f3a79806c12f19cd631ba19d18ca9ad9eebc83d51` |
| integrity-case-004 | 49.0 | 85.7 (invalid) | 58.9 | 100.0 (valid) | [artifacts/integrity-case-004.json](artifacts/integrity-case-004.json) `a80258776c5fc32e15833237e8cde8f3944f32b85a8aeccae50a82ce877a10e6` |
| integrity-case-005 | 57.5 | 65.6 (invalid) | 55.1 | 87.5 (valid_with_warnings) | [artifacts/integrity-case-005.json](artifacts/integrity-case-005.json) `7d83fda292509f41ec2ca4dab5929fa8a4508f32cfb20486417ef038cd2f44ae` |
| integrity-case-006 | 28.5 | 75.0 (invalid) | 58.4 | 100.0 (valid) | [artifacts/integrity-case-006.json](artifacts/integrity-case-006.json) `e472f86f28ff3c859b4079d66e543f3f3b1f087209525bd0d00b80b54296931c` |
| integrity-case-007 | 27.0 | 91.7 (invalid) | 40.0 | 100.0 (valid) | [artifacts/integrity-case-007.json](artifacts/integrity-case-007.json) `a84d69b177110bc2bad96a74487d570a0005d4a5234d4e8e85a3ae33c8207bbf` |
| integrity-case-008 | 40.5 | 91.7 (invalid) | 39.0 | 100.0 (valid) | [artifacts/integrity-case-008.json](artifacts/integrity-case-008.json) `9f0d8699a5533368ec44b5bb10bde8113170a390f03ddc52e874f8a534afa315` |
| integrity-case-009 | 35.2 | 91.7 (invalid) | 30.5 | 100.0 (valid) | [artifacts/integrity-case-009.json](artifacts/integrity-case-009.json) `0fa38e37756215e5b7acc8d452d9ad05cafcef7b9ae9a86e15c6831790cefa0e` |
| integrity-case-010 | N/A | N/A | N/A | N/A (invalid) | [artifacts/integrity-case-010.json](artifacts/integrity-case-010.json) `8f148ed2958246280037078b16cc23875ac3d7a2507f1f5c5dd5a170e5e8ff11` |
| integrity-case-011 | 53.6 | 10.0 (invalid) | 67.4 | 100.0 (valid) | [artifacts/integrity-case-011.json](artifacts/integrity-case-011.json) `f0b3825c44a5c76e6b42e171a9745433486220213b1c30b474059b1a6dae404b` |
| integrity-case-012 | N/A | N/A | N/A | N/A (invalid) | [artifacts/integrity-case-012.json](artifacts/integrity-case-012.json) `284d5efe672572e800b1d72358e33cc4f6dc5cdca58d13e1ee1b87bedda3a1a0` |
| integrity-case-013 | N/A | N/A | N/A | N/A (invalid) | [artifacts/integrity-case-013.json](artifacts/integrity-case-013.json) `19dc30f587794d42c66e35090e61b4b2d9b2e1d89a1099184806eedda1928856` |
| synthetic-invalid-number | 63.6 | 42.5 (invalid) | 72.7 | 90.0 (valid_with_warnings) | [artifacts/synthetic-invalid-number.json](artifacts/synthetic-invalid-number.json) `aacb1222996d31722e8c9bb162ab05d90cf32ba508a1a678f058e20505623290` |
| synthetic-valid | 78.0 | 90.0 (valid_with_warnings) | 78.0 | 90.0 (valid_with_warnings) | [artifacts/synthetic-valid.json](artifacts/synthetic-valid.json) `a724d75b1e6372c64745918b9830e5ba99649cef1b892d377c323a846a2b264e` |
