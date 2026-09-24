#include <bout/derivs.hxx>
#include <bout/field_factory.hxx>
#include <bout/initialprofiles.hxx>
#include <bout/invert_laplace.hxx>
#include <bout/physicsmodel.hxx>

class TCTCurrentSheet : public PhysicsModel {
private:
  Field3D psi;
  Field3D omega;
  Field3D phi;
  Field3D phi_plasma;
  Field3D electrode_profile;
  Field3D electrode_phi;
  Field3D J;
  Field3D tct_mask;

  BoutReal eta;
  BoutReal nu;
  BoutReal tct_strength;
  BoutReal omega_tct_strength;
  BoutReal electrode_strength;
  BoutReal tct_start_time;
  BoutReal tct_end_time;
  bool feedback_enabled;
  int feedback_mode;
  BoutReal feedback_threshold;
  BoutReal feedback_delay;
  BoutReal feedback_min_time;
  BoutReal feedback_noise_fraction;
  BoutReal feedback_trigger_time;
  BoutReal feedback_observable;
  BoutReal feedback_signal;
  BoutReal feedback_growth_rate;
  BoutReal feedback_gate;
  BoutReal previous_feedback_time;
  BoutReal previous_feedback_observable;
  BRACKET_METHOD bracket_method;

  std::unique_ptr<Laplacian> phi_solver;

protected:
  int init(bool UNUSED(restarting)) override {
    auto& options = Options::root()["tct"];
    eta = options["eta"].doc("Magnetic diffusivity").withDefault(1e-3);
    nu = options["nu"].doc("Vorticity viscosity").withDefault(1e-3);
    tct_strength = options["strength"].doc("Localized psi actuator damping").withDefault(0.0);
    omega_tct_strength =
        options["omega_strength"].doc("Localized vorticity actuator damping").withDefault(0.0);
    electrode_strength = options["electrode_strength"]
                             .doc("Amplitude of imposed segmented-electrode potential profile")
                             .withDefault(0.0);
    tct_start_time = options["start_time"].doc("TCT actuator turn-on time").withDefault(0.0);
    tct_end_time = options["end_time"].doc("TCT actuator turn-off time").withDefault(1e30);
    feedback_enabled = options["feedback_enabled"].doc("Enable max-vorticity threshold feedback").withDefault(false);
    feedback_mode = options["feedback_mode"].doc("0=max-vorticity magnitude, 1=max-vorticity growth rate").withDefault(0);
    feedback_threshold = options["feedback_threshold"].doc("Measured max-vorticity trigger threshold").withDefault(0.02);
    feedback_delay = options["feedback_delay"].doc("Actuator delay after threshold crossing").withDefault(0.0);
    feedback_min_time = options["feedback_min_time"].doc("Minimum observation time before feedback can trigger").withDefault(0.0);
    feedback_noise_fraction = options["feedback_noise_fraction"].doc("Deterministic sensor-noise fraction").withDefault(0.0);
    feedback_trigger_time = -1.0;
    feedback_observable = 0.0;
    feedback_signal = 0.0;
    feedback_growth_rate = 0.0;
    feedback_gate = 0.0;
    previous_feedback_time = -1.0;
    previous_feedback_observable = 0.0;

    switch (options["bracket"].withDefault(2)) {
    case 0:
      bracket_method = BRACKET_STD;
      break;
    case 1:
      bracket_method = BRACKET_SIMPLE;
      break;
    case 2:
      bracket_method = BRACKET_ARAKAWA;
      break;
    default:
      output << "ERROR: Invalid bracket option. Use 0, 1, or 2.\n";
      return 1;
    }

    tct_mask.setBoundary("tct_mask");
    initial_profile("tct_mask", tct_mask);
    tct_mask.applyBoundary();

    // Signed, resolved electrode-voltage shape. Segmentation is encoded in this
    // profile rather than collapsed to a peak-shear scalar. electrode_strength
    // is a pure amplitude multiplier, so electrode_strength=0 is algebraically
    // identical to the pre-electrode model and can be runtime zero-equivalence tested.
    electrode_profile.setBoundary("electrode_profile");
    initial_profile("electrode_profile", electrode_profile);
    electrode_profile.applyBoundary();

    phi_solver = Laplacian::create();
    phi = 0.0;
    phi_plasma = 0.0;
    electrode_phi = 0.0;

    SOLVE_FOR(psi, omega);

    mesh->communicate(psi);
    J = -Delp2(psi);

    return 0;
  }

  void outputVars(Options& state) override {
    state["phi"].assignRepeat(phi).setAttributes({{"long_name", "Total electrostatic potential"}});
    state["phi_plasma"].assignRepeat(phi_plasma).setAttributes({{"long_name", "Vorticity-inverted plasma electrostatic potential"}});
    state["electrode_phi"].assignRepeat(electrode_phi).setAttributes({{"long_name", "Imposed segmented-electrode potential"}});
    state["electrode_profile"].assignRepeat(electrode_profile).setAttributes({{"long_name", "Signed segmented-electrode spatial profile"}});
    state["J"].assignRepeat(J).setAttributes({{"long_name", "Current density proxy"}});
    state["tct_mask"].assignRepeat(tct_mask).setAttributes({{"long_name", "Resolved TCT actuator mask"}});
    state["feedback_observable"].assignRepeat(feedback_observable).setAttributes(
        {{"long_name", "Measured global max-vorticity feedback observable"}});
    state["feedback_signal"].assignRepeat(feedback_signal).setAttributes(
        {{"long_name", "Closed-loop threshold signal"}});
    state["feedback_growth_rate"].assignRepeat(feedback_growth_rate).setAttributes(
        {{"long_name", "Measured max-vorticity growth-rate signal"}});
    state["feedback_gate"].assignRepeat(feedback_gate).setAttributes(
        {{"long_name", "Closed-loop TCT actuator gate"}});
    state["feedback_trigger_time"].assignRepeat(feedback_trigger_time).setAttributes(
        {{"long_name", "Closed-loop threshold crossing time"}});
  }

  int rhs(BoutReal time) override {
    // Keep the inverted plasma potential separate from imposed electrode potential.
    // This prevents the electrode field from becoming the Laplacian solver's next
    // initial guess and makes the zero-strength handoff explicit.
    phi_plasma = phi_solver->solve(omega, phi_plasma);

    const BoutReal time_gate = (time >= tct_start_time && time <= tct_end_time) ? 1.0 : 0.0;

    mesh->communicate(psi, omega, phi_plasma, tct_mask, electrode_profile);
    J = -Delp2(psi);
    mesh->communicate(J);

    feedback_observable =
        max(abs(omega), true) * (1.0 + feedback_noise_fraction * sin(1.61803398875 * time));
    if (previous_feedback_time >= 0.0 && time > previous_feedback_time) {
      feedback_growth_rate =
          (feedback_observable - previous_feedback_observable) / (time - previous_feedback_time);
      previous_feedback_time = time;
      previous_feedback_observable = feedback_observable;
    } else if (previous_feedback_time < 0.0) {
      previous_feedback_time = time;
      previous_feedback_observable = feedback_observable;
      feedback_growth_rate = 0.0;
    }
    feedback_signal = feedback_mode == 1 ? feedback_growth_rate : feedback_observable;
    if (feedback_enabled && feedback_trigger_time < 0.0 && time >= feedback_min_time
        && feedback_signal >= feedback_threshold) {
      feedback_trigger_time = time;
    }

    feedback_gate = feedback_enabled && feedback_trigger_time >= 0.0
                            && time >= feedback_trigger_time + feedback_delay
                        ? 1.0
                        : 0.0;
    const BoutReal actuator_gate = feedback_enabled ? feedback_gate : time_gate;

    // The imposed potential enters the same phi used by the Poisson brackets,
    // producing resolved E x B advection without modifying eta, nu, or the legacy
    // psi/omega actuator terms. Signed/multi-zone structure remains spatially explicit.
    electrode_phi = actuator_gate * electrode_strength * electrode_profile;
    phi = phi_plasma + electrode_phi;
    mesh->communicate(phi, electrode_phi);

    ddt(psi) = -bracket(phi, psi, bracket_method) + eta * Delp2(psi)
               - actuator_gate * tct_strength * tct_mask * psi;

    ddt(omega) = -bracket(phi, omega, bracket_method) + bracket(J, psi, bracket_method)
                 + nu * Delp2(omega) - actuator_gate * omega_tct_strength * tct_mask * omega;

    return 0;
  }
};

BOUTMAIN(TCTCurrentSheet);
