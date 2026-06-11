#include <bout/derivs.hxx>
#include <bout/physicsmodel.hxx>

class DIIIDOperatorProbe : public PhysicsModel {
private:
  Field3D state;
  Field3D psi;
  Field3D one;
  Field3D ddx_psi;
  Field3D ddy_psi;
  Field3D gradpar_psi;
  Field3D delp2_one;
  Field3D bracket_self;

protected:
  int init(bool UNUSED(restarting)) override {
    Field2D psi2d;
    mesh->get(psi2d, "psixy");
    psi = psi2d;
    one = 1.0;
    mesh->communicate(psi, one);

    ddx_psi = DDX(psi);
    ddy_psi = DDY(psi);
    gradpar_psi = Grad_par(psi);
    delp2_one = Delp2(one);
    bracket_self = bracket(psi, psi, BRACKET_ARAKAWA);

    SAVE_ONCE(psi, ddx_psi, ddy_psi, gradpar_psi, delp2_one, bracket_self);
    SOLVE_FOR(state);
    return 0;
  }

  int rhs(BoutReal UNUSED(time)) override {
    ddt(state) = 0.0;
    return 0;
  }
};

BOUTMAIN(DIIIDOperatorProbe);
