# Plasma Channel Architecture Diagrams

These diagrams are conceptual only. They are intended to communicate architecture and control logic, not final engineering geometry.

## Functional channel map

```mermaid
flowchart LR
    CORE[Main burn channel\nthermal ions + fusion core]
    SHEAR[TCT / shear boundary\ncurrent-sheet stability control]
    ALPHA[Alpha extraction lane\nfast charged products]
    ELEC[Hot-electron exhaust lane\nRF / E×B biased]
    ASH[Impurity / ash exhaust lane\nSOL + divertor routing]
    WALL[Liquid lithium + Be/B4C/graphene-backed wall\nheat and particle sink]
    DC[Direct conversion electrodes\nstaged deceleration]
    DIV[Boron vapor / p-B11 edge cavity\noptional later-stage subsystem]

    CORE --> SHEAR
    SHEAR --> ALPHA
    SHEAR --> ELEC
    SHEAR --> ASH
    ALPHA --> DC
    ELEC --> WALL
    ASH --> WALL
    CORE --> DIV
    DIV --> ALPHA
    DIV --> WALL
```

## Control stack

```mermaid
flowchart TD
    DIAG[Diagnostics\nmagnetic probes, radiation, heat flux, density]
    SUP[TCT supervisor\ninstability severity control]
    MAG[Magnetic topology\nq-profile, islands, mirror/cusp pockets]
    RF[RF / wave control\nselective particle interaction]
    EB[E-fields / biasing\nE×B drift control]
    LL[Liquid lithium wall\nMHD shaping + heat sink]
    OUT[Outputs\npass rate, burst rate, heat load, alpha extraction, Pnet proxy]

    DIAG --> SUP
    SUP --> MAG
    SUP --> RF
    SUP --> EB
    SUP --> LL
    MAG --> OUT
    RF --> OUT
    EB --> OUT
    LL --> OUT
    OUT --> DIAG
```

## Development sequence

```mermaid
flowchart TD
    A[TCT-stabilized core + controlled edge]
    B[Liquid lithium wall + impurity sink]
    C[Hot-electron exhaust proxy]
    D[Alpha-channeling / direct conversion proxy]
    E[Boron vapor / p-B11 resonator cavity]
    F[Integrated four-channel architecture]

    A --> B --> C --> D --> E --> F
```

## Conceptual radial layering

```text
                 Plasma / reactor cross-section concept

       -----------------------------------------------------
       | Outer structure / neutron + heat management        |
       |   Be / B4C / SiC-compatible support layer          |
       |   graphene-channel thermal spreader layer          |
       |   flowing liquid lithium wall / breeder / getter   |
       |---------------------------------------------------|
       | scrape-off / impurity / ash exhaust lane           |
       |---------------------------------------------------|
       | hot-electron biased exhaust / radiative edge       |
       |---------------------------------------------------|
       | alpha extraction / direct conversion access lane   |
       |---------------------------------------------------|
       | main burn channel + TCT-stabilized shear boundary  |
       -----------------------------------------------------
```

## Important interpretation

The word “channel” means a preferred transport route in phase space and magnetic topology. It does **not** mean a rigid physical pipe inside the plasma.
