import math

MU0 = 4*math.pi*1e-7

# engineering limits
MAX_WALL_LOAD = 20        # MW/m² advanced liquid wall
MAX_STRESS = 7e8          # 700 MPa
MAX_HEAT_EXTRACTION = 5e4 # MW

def magnet_stress(B0, R):

    # toroidal magnetic pressure
    pressure = (B0**2) / (2*MU0)

    # approximate hoop stress
    stress = pressure * R

    return stress


def wall_heat_flux(pfus, R, a):

    area = 4*(math.pi**2)*R*a

    # ~80% fusion energy goes to neutrons
    neutron_power = 0.8 * pfus

    return neutron_power / area


def cooling_limit(pfus):

    # rough Brayton cycle scaling
    efficiency = 0.45

    thermal = pfus / efficiency

    return thermal


def engineering_penalty(design, plasma):

    pfus = plasma["pfus"]
    R = design["R"]
    a = design["a"]
    B0 = design["B0"]

    penalty = 0

    # wall heat constraint
    wall = wall_heat_flux(pfus, R, a)

    if wall > MAX_WALL_LOAD:
        penalty += (wall - MAX_WALL_LOAD) * 50

    # magnet stress constraint
    stress = magnet_stress(B0, R)

    if stress > MAX_STRESS:
        penalty += (stress - MAX_STRESS) / 1e7

    # plant heat removal constraint
    thermal = cooling_limit(pfus)

    if thermal > MAX_HEAT_EXTRACTION:
        penalty += (thermal - MAX_HEAT_EXTRACTION) * 0.01

    return penalty, wall, stress
