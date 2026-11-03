# Mesh Provenance Comparison

| item | historical/single-part path | checked-in 48-part path |
|---|---|---|
| partition count | 1 stored file | 48 stored files |
| source commit | `496ddb1f` restored .smb after `cce2de4a`; test introduced `e68a254d` | `62d5cbc7` |
| total file size | 175447 | 215876 |
| sha256 | `4647bb086e4d40d25bf8b3be93153c3da073b4519eefbfe9a073d1dbd71de921` | see `mesh_sha256.txt` |
| entity counts | v 1323, e 3841, f 2519, r 0 in diagnostic run | v 1323, e 3841, f 2519, r 0 in 48-rank run |
| partition balance | one rank owns all 2519 faces | 49-55 local faces per rank from stdout |
| current runtime behavior | upstream C1ke compare passes | upstream C1ke compare fails at t=0 on `emagp`; `Volume=0` |
| metadata/provenance | old `part_mesh.sh` makes `model.dmg` with `make_model` then calls `split_smb model.dmg mesh.smb part.smb factor` | current public tree includes generated part files, but no contemporaneous C1ke update |

Historical split recovery: `make_model` compiled and ran with modern PUMI, producing `model.dmg`. The historical `split_smb` source compiled, but aborted during the PUMI/Zoltan split under PUMI 2.2.9, so a faithful regenerated 48-way mesh was not produced in this environment.
