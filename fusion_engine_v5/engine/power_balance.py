def thermal_conversion_efficiency(coolant_outlet_K, base_eff=0.42):
    modifier = 1.0 + 0.0002 * (coolant_outlet_K - 900.0)
    eff = base_eff * modifier
    return max(0.25, min(eff, 0.55))

def plant_power_balance(plasma, blanket, mhd_power_mw, design):
    pfus = plasma["pfus_mw"]
    pbrem = plasma["pbrem_mw"]
    ptr = plasma["ptr_mw"]
    current_drive = plasma["current_drive_mw"]
    pump = design.get("pump_power_mw", 0.0)

    thermal_to_balance = pfus - pbrem - ptr - mhd_power_mw - pump - current_drive
    eff = thermal_conversion_efficiency(design.get("coolant_outlet_K", 900.0), design.get("cooling_eff", 0.42))
    net_electric = eff * thermal_to_balance
    return {
        "thermal_balance_mw": thermal_to_balance,
        "conversion_eff": eff,
        "current_drive_mw": current_drive,
        "pump_power_mw": pump,
        "mhd_power_mw": mhd_power_mw,
        "net_electric": net_electric,
    }
