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
  Field3D J;
  Field3D tct_mask;

  BoutReal eta;
  BoutReal nu;
  BoutReal tct_strength;
  BoutReal omega_tct_strength;
  BoutReal tct_start_time;
  BoutReal tct_end_time;
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
    tct_start_time = options["start_time"].doc("TCT actuator turn-on time").withDefault(0.0);
    tct_end_time = options["end_time"].doc("TCT actuator turn-off time").withDefault(1e30);

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

    phi_solver = Laplacian::create();
    phi = 0.0;

    SOLVE_FOR(psi, omega);

    mesh->communicate(psi);
    J = -Delp2(psi);

    return 0;
  }

  void outputVars(Options& state) override {
    state["phi"].assignRepeat(phi).setAttributes({{"long_name", "Electrostatic potential"}});
    state["J"].assignRepeat(J).setAttributes({{"long_name", "Current density proxy"}});
    state["tct_mask"].assignRepeat(tct_mask).setAttributes({{"long_name", "Resolved TCT actuator mask"}});
  }

  int rhs(BoutReal time) override {
    phi = phi_solver->solve(omega, phi);

    mesh->communicate(psi, omega, phi, tct_mask);
    J = -Delp2(psi);
    mesh->communicate(J);

    const BoutReal actuator_gate = (time >= tct_start_time && time <= tct_end_time) ? 1.0 : 0.0;

    ddt(psi) = -bracket(phi, psi, bracket_method) + eta * Delp2(psi)
               - actuator_gate * tct_strength * tct_mask * psi;

    ddt(omega) = -bracket(phi, omega, bracket_method) + bracket(J, psi, bracket_method)
                 + nu * Delp2(omega) - actuator_gate * omega_tct_strength * tct_mask * omega;

    return 0;
  }
};

BOUTMAIN(TCTCurrentSheet);
