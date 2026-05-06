import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ---------------------------------------------------------
# GEOMETRY + PHYSICS
# ---------------------------------------------------------

def plasma_volume(R,a,kappa):
    return 2.0*(math.pi**2)*R*(a**2)*kappa

def first_wall_area(R,a):
    return 4.0*(math.pi**2)*R*a

def greenwald_density(Ip,a):
    return (Ip/(math.pi*a*a))*1e20

def reactivity_dt(T):
    T=max(float(T),1e-9)
    return 5e-22*(T**2)*math.exp(-19.94/(T**(1/3)))

# ---------------------------------------------------------
# CORE PLASMA MODEL
# ---------------------------------------------------------

def evaluate_case(
    R_m,
    a_m,
    kappa,
    B0_T,
    Ip_MA,
    Ti_keV,
    Te_keV,
    H98,
    f_greenwald,
    frac_cap
):

    V=plasma_volume(R_m,a_m,kappa)
    A=first_wall_area(R_m,a_m)

    nG=greenwald_density(Ip_MA,a_m)
    ne=frac_cap*f_greenwald*nG

    sv=reactivity_dt(Ti_keV)

    pfus=(0.25*ne**2*sv*17.6*1.602e-13)*V/1e6

    pbrem=(5.35e-37*ne**2*math.sqrt(Te_keV*1e3))*V/1e6

    Wth=1.5*(2*ne*Ti_keV*1e3)*1.602e-19

    tauE=H98*1.39

    ptr=(Wth/tauE)*V/1e6

    wn=(0.8*pfus)/A

    p_pa=(2.0*ne*Ti_keV*1e3)*1.602e-19

    beta=(2*4e-7*math.pi*p_pa)/(B0_T**2)

    betaN=100*beta*a_m*B0_T/Ip_MA

    qstar=(5*a_m*a_m*B0_T)/(R_m*Ip_MA)*(1+kappa**2)/2

    return {
        "pfus_mw":pfus,
        "pbrem_mw":pbrem,
        "ptr_mw":ptr,
        "wn_mw_m2":wn,
        "betaN":betaN,
        "qstar":qstar,
        "ne_m3":ne,
        "V_m3":V
    }

# ---------------------------------------------------------
# WALL MODEL
# ---------------------------------------------------------

def lithium_wall_temperature(heat_flux,thickness):

    k_li=84.0

    return heat_flux*thickness/k_li

# ---------------------------------------------------------
# ELM MODEL
# ---------------------------------------------------------

def simulate_elm(rng,plasma_energy,controller_active):

    base_prob=0.05

    if rng.random()>base_prob:
        return 0.0,False

    elm_fraction=rng.uniform(0.05,0.15)

    elm_energy=plasma_energy*elm_fraction

    if controller_active:
        elm_energy*=0.2

    strike_area=10.0

    energy_density=elm_energy/strike_area

    return energy_density/1e6,True

# ---------------------------------------------------------
# TCT MONTE CARLO
# ---------------------------------------------------------

def robustness_monte_carlo(
    base_params,
    N=10000,
    seed=1,
    reconn_trigger=0.7,
    conf_trigger=0.7
):

    rng=np.random.default_rng(seed)

    res0=evaluate_case(**base_params)

    pfus0=res0["pfus_mw"]
    pbrem0=res0["pbrem_mw"]
    ptr0=res0["ptr_mw"]

    rows=[]
    engage_count=0
    burst_count=0
    wall_damage=0

    for i in range(N):

        H_mult=rng.uniform(0.65,1.05)
        R_mult=rng.uniform(1.0,2.5)
        F_mult=rng.uniform(0.6,1.0)

        risk_R=(R_mult-1)/1.5
        risk_H=(1.05-H_mult)/0.4

        engaged=(risk_R>reconn_trigger or risk_H>conf_trigger)

        if engaged:
            engage_count+=1
            effort=max(risk_R,risk_H)
            R_mult*=1-0.75*effort
            H_mult*=1+0.25*effort

        burst=rng.random()<0.08
        if burst:
            burst_count+=1

        burst_mult=1.8 if burst else 1

        pfus=pfus0*F_mult

        ploss=(pbrem0*burst_mult)+(ptr0/H_mult)+(558*R_mult)

        pnet=pfus-ploss

        # plasma stored energy
        plasma_energy=5e8

        elm_density,elm=simulate_elm(rng,plasma_energy,engaged)

        if elm_density>0.8:
            wall_damage+=1

        rows.append({
            "pnet_mw":pnet,
            "elm_energy_MJ_m2":elm_density
        })

    df=pd.DataFrame(rows)

    summary={
        "pnet_p50":df["pnet_mw"].median(),
        "pnet_p05":df["pnet_mw"].quantile(0.05),
        "engage_rate":engage_count/N,
        "burst_rate":burst_count/N,
        "fail_rate":(df["pnet_mw"]<=0).mean(),
        "wall_damage_rate":wall_damage/N
    }

    return summary,df

# ---------------------------------------------------------
# BASELINE
# ---------------------------------------------------------

base_params={
    "R_m":8.1375,
    "a_m":2.53617,
    "kappa":2.0,
    "B0_T":6.125,
    "Ip_MA":23.5,
    "Ti_keV":28.7368,
    "Te_keV":15.2631,
    "H98":1.25,
    "f_greenwald":0.8,
    "frac_cap":0.72
}

# ---------------------------------------------------------
# THRESHOLD SCAN
# ---------------------------------------------------------

print("Running threshold scan")

triggers=np.arange(0.6,0.71,0.01)

results=[]

for t in triggers:

    summary,_=robustness_monte_carlo(
        base_params,
        N=20000,
        reconn_trigger=t
    )

    results.append({
        "trigger":t,
        "p05":summary["pnet_p05"],
        "fail":summary["fail_rate"],
        "engage":summary["engage_rate"],
        "wall_damage":summary["wall_damage_rate"]
    })

df=pd.DataFrame(results)

df.to_csv("tct_scan_results.csv",index=False)

# ---------------------------------------------------------
# PLOTS
# ---------------------------------------------------------

plt.figure()

plt.plot(df["trigger"],df["p05"],label="Pnet P05")
plt.plot(df["trigger"],df["fail"],label="Fail Rate")
plt.plot(df["trigger"],df["wall_damage"],label="Wall Damage")

plt.legend()

plt.xlabel("Reconnection Trigger")

plt.ylabel("Metric")

plt.title("TCT Threshold Scan")

plt.savefig("tct_scan_plot.png")

plt.show()

print("Done.")
