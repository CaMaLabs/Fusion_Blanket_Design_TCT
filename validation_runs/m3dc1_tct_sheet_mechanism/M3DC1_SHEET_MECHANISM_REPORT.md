# M3D-C1 Static Sheet Mechanism Result

Classification: `M3DC1_SHEET_BROADENING_RAPIDLY_RELAXES`

Qualification: `TARGET_FIELD_LEVEL_BROADENING_NOT_CLEANLY_ACHIEVED`

The requested analytic GEM equilibrium change was a current-conserving +10% sheet-width broadening:

- baseline analytic FWHM: `0.8813735870195432`
- broadened analytic FWHM: `0.9695109457214975`
- requested analytic broadening: `10.0%`
- analytic integrated sheet-current conservation error: `0.0`

The native coarse field representation did not cleanly realize that target:

- measured field-level width gain at `t=0`: `0.21624622297935267%`
- local weighted signed sheet-current change at `t=0`: `8.68801518987641%`
- local weighted absolute sheet-current change at `t=0`: `8.577441477203632%`
- central peak `|jphi|` was initially lower by `5.095178315228531%`

The unsupported broadening was rapidly erased and inverted by native GEM dynamics:

- first post-initialization output time: `t=0.05`
- width change at `t=0.05`: `-3.437765200259841%`
- peak `|jphi|` change at `t=0.05`: `+13.764267630486485%`
- worst post-`t=0` width change: `-3.647188452376195%`
- post-`t=0` integrated absolute sheet-current loading change: `+11.960051863750056%`

Topology/reconnection did not show a compensating success:

- peak reconnection-rate proxy change: `-2.2964670086615457%`
- final `Reconnected_Flux` change: `+0.9490960239952599%`
- topology event timing shift: `0.0`
- island width was not robustly derivable from the coarse scalar/element-center output; X/O scalars were tracked instead

Interpretation: this does not falsify the current-sheet broadening mechanism. It shows that a one-time unsupported initialization is rapidly reorganized by native M3D-C1, and the field-level target broadening was not cleanly achieved.
