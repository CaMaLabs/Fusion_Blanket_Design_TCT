MATERIALS = {
    "W": {"density": 19.3, "porous_ok": False, "components": [("nuclide","W182",0.265,"ao"),("nuclide","W183",0.143,"ao"),("nuclide","W184",0.306,"ao"),("nuclide","W186",0.286,"ao")]},
    "Be": {"density":1.85,"porous_ok":True,"components":[("nuclide","Be9",1.0,"ao")]},
    "Be12Ti": {"density":2.24,"porous_ok":True,"components":[("nuclide","Be9",12.0,"ao"),("element","Ti",1.0,"ao")]},
    "B4C": {"density":2.52,"porous_ok":True,"components":[("element","B",4.0,"ao"),("element","C",1.0,"ao")]},
    "SiC": {"density":3.21,"porous_ok":True,"components":[("element","Si",1.0,"ao"),("element","C",1.0,"ao")]},
    "TiB2": {"density":4.52,"porous_ok":True,"components":[("element","Ti",1.0,"ao"),("element","B",2.0,"ao")]},
    "Pb": {"density":11.34,"porous_ok":False,"components":[("element","Pb",1.0,"ao")]},
    "PbLi": {"density":9.8,"porous_ok":False,"components":[("element","Pb",0.83,"ao"),("nuclide","Li6",0.153,"ao"),("nuclide","Li7",0.017,"ao")]},
    "Li": {"density":0.534,"porous_ok":False,"components":[("nuclide","Li6",0.9,"ao"),("nuclide","Li7",0.1,"ao")]},
    "Li2O": {"density":2.01,"porous_ok":True,"components":[("nuclide","Li6",1.8,"ao"),("nuclide","Li7",0.2,"ao"),("element","O",1.0,"ao")]},
    "Li2TiO3": {"density":3.43,"porous_ok":True,"components":[("nuclide","Li6",1.8,"ao"),("nuclide","Li7",0.2,"ao"),("element","Ti",1.0,"ao"),("element","O",3.0,"ao")]},
    "Li4SiO4": {"density":2.39,"porous_ok":True,"components":[("nuclide","Li6",3.6,"ao"),("nuclide","Li7",0.4,"ao"),("element","Si",1.0,"ao"),("element","O",4.0,"ao")]},
    "W_Ti_B4C_60_30_10_wt": {"density":13.45,"porous_ok":False,"components":[("element","W",0.60,"wo"),("element","Ti",0.30,"wo"),("element","B",0.07826,"wo"),("element","C",0.02174,"wo")]},
    "W_Ti_B4C_Cr_55_25_10_10_wt": {"density":12.78,"porous_ok":False,"components":[("element","W",0.55,"wo"),("element","Ti",0.25,"wo"),("element","B",0.07826,"wo"),("element","C",0.02174,"wo"),("element","Cr",0.10,"wo")]},
}

BLANKET_CANDIDATES = list(MATERIALS.keys())

def uses_lithium(name):
    return any(c[0] == "nuclide" and c[1] in ("Li6","Li7") for c in MATERIALS[name]["components"])

def porous_ok(name):
    return MATERIALS[name]["porous_ok"]
