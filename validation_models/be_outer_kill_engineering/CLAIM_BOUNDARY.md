# Claim Boundary — `be_outer_kill` Engineering Degradation

This validation family is allowed to support only the following claim:

> A reproducible OpenMC sensitivity workflow exists to compare the current
> idealized `be_outer_kill` material ordering against reduced engineering cases
> that explicitly consume blanket volume with structure, coolant channels,
> finite radial penetrations, and shielding, while reporting transport-seed and
> tally uncertainty.

It is **not** evidence that:

- the geometry is a final tokamak blanket sector,
- TBR remains adequate after real CAD integration,
- coolant layout is thermohydraulically viable,
- structural material survives neutron damage or thermal stress,
- the ports reproduce real diagnostic/heating penetrations,
- shielding is sufficient for magnets or personnel,
- tritium extraction/inventory is closed,
- the blanket is maintainable or manufacturable,
- D is closed.

A result may narrow D by measuring the penalty introduced by the declared
parasitics. Promotion beyond `ENGINEERING_DEGRADATION_SCREEN_ONLY` requires a
CAD/sector neutronics case with documented real penetrations/supports followed
by coupled engineering validation.
