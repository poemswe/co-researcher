# Evaluation Run run_20261007_143121_203203

**Evaluation**: Paired quality and integrity evaluation  
**Capability**: literature-review-integrity  
**Model**: claude:opus  
**Timestamp**: 2026-10-07T14:31:21.203614Z  
**Target commit**: eca0b3715458e463e44530b4ba0780625113a61c (clean)  
**Engine**: 1.0.0 (artifact_scoring=1.0.0, citation=1.0.0, claims=1.0.0, prisma=1.0.0)  
**Resolved model**: claude-opus-5-5  
**Cases**: 15  
**Final integrity statuses**: valid=7, valid_with_warnings=3, invalid=5

Quality and integrity are separate measurements. The integrity status does not imply that the quality score passed a quality threshold.

| Case | First-pass quality | First-pass integrity | Final quality | Final integrity | Validated artifact (SHA-256) |
|---|---:|---:|---:|---:|---|
| integrity-case-001 | 40.5 | 71.4 (invalid) | 55.4 | 100.0 (valid) | [artifacts/integrity-case-001.json](artifacts/integrity-case-001.json) `6704ec31f59b8386ac4375fe8028c3fa1b7af191cde2f5c31668f6bb90cb048e` |
| integrity-case-002 | 34.2 | 71.4 (invalid) | 52.0 | 100.0 (valid) | [artifacts/integrity-case-002.json](artifacts/integrity-case-002.json) `35c303cb3f0f0fa1b02f9dbee60d2d83b1e98feefdbcd547fb213fbc6e02f6a9` |
| integrity-case-003 | 41.0 | 71.4 (invalid) | 44.0 | 100.0 (valid) | [artifacts/integrity-case-003.json](artifacts/integrity-case-003.json) `59a5e1754053bde91890f7f9810e628feeb9198461643f6a0dc03317c74928fa` |
| integrity-case-004 | 25.5 | 85.7 (invalid) | 43.4 | 100.0 (valid) | [artifacts/integrity-case-004.json](artifacts/integrity-case-004.json) `99a971989f785cf6ca2ab2bf17dc5ec102b204d4966e215d64d03c811682de44` |
| integrity-case-005 | 41.0 | 65.6 (invalid) | 41.0 | 87.5 (valid_with_warnings) | [artifacts/integrity-case-005.json](artifacts/integrity-case-005.json) `d4c5c5ab98b85d3207e81e7698eb31b3a3a9428d18ac539c656631f1057374aa` |
| integrity-case-006 | 34.6 | 75.0 (invalid) | 40.0 | 100.0 (valid) | [artifacts/integrity-case-006.json](artifacts/integrity-case-006.json) `ac725e228d0f71f22511cffc1081ac95f9a212e0a471c64b8e731bb2bd8ec4ca` |
| integrity-case-007 | 29.5 | 91.7 (invalid) | 26.0 | 100.0 (valid) | [artifacts/integrity-case-007.json](artifacts/integrity-case-007.json) `fcea8bfa6efcf9860dcab84c091af976bf0985f6e6266b6c73f2298efdfd46e5` |
| integrity-case-008 | 25.0 | 91.7 (invalid) | 38.5 | 100.0 (valid) | [artifacts/integrity-case-008.json](artifacts/integrity-case-008.json) `395f1e4f16bac246de0823bdf98a004dc0d1ba590665c8bedb4009b98b81eee1` |
| integrity-case-009 | 31.0 | 91.7 (invalid) | 33.1 | 91.7 (invalid) | [artifacts/integrity-case-009.json](artifacts/integrity-case-009.json) `7104591f15a7930d69c842db5c0344cac1e14c1882660fccd6ad5be68cdbb483` |
| integrity-case-010 | N/A | N/A | N/A | N/A (invalid) | [artifacts/integrity-case-010.json](artifacts/integrity-case-010.json) `0f4f75e478ea33d6c1adc26570061b59ac1eb88568244893cb8a458cf84566e5` |
| integrity-case-011 | 40.5 | 10.0 (invalid) | 60.5 | 10.0 (invalid) | [artifacts/integrity-case-011.json](artifacts/integrity-case-011.json) `2e531e6922bf90fa1e74016fbcb086e409dffd5d2a39cb8c2cb9db1ee33042d3` |
| integrity-case-012 | N/A | N/A | N/A | N/A (invalid) | [artifacts/integrity-case-012.json](artifacts/integrity-case-012.json) `9c446a12f254a3ce50490e340879cd40482b341407175068d878ba72084adeaf` |
| integrity-case-013 | N/A | N/A | N/A | N/A (invalid) | [artifacts/integrity-case-013.json](artifacts/integrity-case-013.json) `6af0d2b6e397711ae18382fcc6087baacf86a4431931284d33f4db3ff3824779` |
| synthetic-invalid-number | 38.0 | 50.0 (invalid) | 71.5 | 90.0 (valid_with_warnings) | [artifacts/synthetic-invalid-number.json](artifacts/synthetic-invalid-number.json) `00eeac3dc33788ac4c3ef38d699297c27d0938846ec47200fcebb84ca8ed4377` |
| synthetic-valid | 80.0 | 90.0 (valid_with_warnings) | 80.0 | 90.0 (valid_with_warnings) | [artifacts/synthetic-valid.json](artifacts/synthetic-valid.json) `ae1ff57130c697c016a959bf003f8bf9bbe01a2054cc4cb25bce44c11dd657f4` |
