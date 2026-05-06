import math

MU0 = 4 * math.pi * 1e-7


# -----------------------------------------------------
# CURRENT DRIVE POWER
# -----------------------------------------------------

def current_drive_power(Ip_MA, B0_T):

    """
    Approximate auxiliary current drive power.
    Scaling based loosely on NBI/ECRH systems.
    """

    efficiency = 0.35

    # MW required to sustain plasma current
    required = 0.25 * Ip_MA * B0_T

    return required / efficiency


# -----------------------------------------------------
# THERMAL POWER CYCLE
# -----------------------------------------------------

def thermal_conversion(pfus):

    """
    Converts fusion power to electrical power.
    """

    thermal_eff = 0.45  # advanced Brayton cycle

    return pfus * thermal_eff


# -----------------------------------------------------
# LIQUID LITHIUM MHD DRAG
# -----------------------------------------------------

def lithium_mhd_drag(B0, velocity=5, channel=0.02):

    """
    Magnetohydrodynamic drag from flowing lithium blanket.
    """

    sigma = 1e6  # lithium electrical conductivity
    rho = 500  # lithium density

    Ha = B0 * channel * math.sqrt(sigma / rho)

    drag = Ha * velocity * 0.002

    return drag


# -----------------------------------------------------
# PUMPING POWER
# -----------------------------------------------------

def pumping_power(pfus):

    """
    Rough estimate of coolant circulation power.
    """

    return 0.02 * pfus


# -----------------------------------------------------
# TOTAL PLANT POWER MODEL
# -----------------------------------------------------

def plant_power_balance(design, plasma):

    pfus = plasma["pfus"]

    electrical = thermal_conversion(pfus)

    current_drive = current_drive_power(
        design["Ip"],
        design["B0"]
    )

    mhd = lithium_mhd_drag(design["B0"])

    pump = pumping_power(pfus)

    parasitic = current_drive + mhd + pump

    net_electric = electrical - parasitic

    return {

        "electric": electrical,
        "current_drive": current_drive,
        "mhd": mhd,
        "pump": pump,
        "net_electric": net_electric
    }
