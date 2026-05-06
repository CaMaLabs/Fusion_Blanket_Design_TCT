def blanket_surrogate(design, plasma):
    li6 = design.get("li6_frac", 0.6)
    mult = design.get("mult_frac", 0.25)
    thickness = design.get("blanket_thickness", 1.0)

    tbr = 0.82 + 0.32 * li6 + 0.26 * mult + 0.18 * (1.0 - pow(2.718281828, -thickness / 0.6))
    tbr = max(0.6, tbr)  # removed upper clamp to allow exploration
    attenuation = 1.0 - 0.65 * (1.0 - pow(2.718281828, -thickness / 0.8))
    blanket_heat_mw = 0.8 * plasma["pfus_mw"] * 0.65
    return {
        "TBR": tbr,
        "attenuation": max(0.05, attenuation),
        "blanket_heat_mw": blanket_heat_mw,
        "front_heating_frac": 0.25,
        "model": "surrogate",
    }
