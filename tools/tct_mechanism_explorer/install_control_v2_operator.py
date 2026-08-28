#!/usr/bin/env python3
"""Install the default-off TCT Control V2 staged magnetic selector in M3D-C1.

This extends the already-local `imag_control` source. With
`imag_control_staged = 0` (default), legacy behavior is unchanged. With staged
mode enabled, the magnetic command follows a predeclared bias -> early ->
aggressive -> hold schedule while the native upstream `ipforce` momentum source
can provide a standing flow/shear-bias audit channel.

The staged selector is baseline-informed open-loop control, not closed-loop
feedback and not a physical liquid-lithium transfer model.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess

SRC = Path(os.environ.get("M3D_ROOT", "/home/ubuntu/M3DC1-official"))
BUILD = Path(os.environ.get("M3D_BUILD", str(SRC / "build-ubuntu-2d")))
EXE = BUILD / "unstructured/m3dc1_2d"


def _read(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(path)
    return path.read_text(encoding="utf-8")


def _write_if_changed(path: Path, old: str, new: str) -> bool:
    if old == new:
        return False
    path.write_text(new, encoding="utf-8")
    return True


def _install_modules(path: Path) -> bool:
    text = _read(path)
    if "imag_control_staged" in text:
        return False
    match = re.search(r"^(\s*real\s*::\s*mag_ctrl_t_off[^\n]*\n)", text, re.M)
    if not match:
        raise RuntimeError("imag_control variable block not found in M3Dmodules.f90")
    addition = (
        match.group(1)
        + "  integer :: imag_control_staged ! 1 = scheduled bias/early/aggressive/hold magnetic command\n"
        + "  real :: mag_ctrl_bias_amp      ! standing magnetic bias before early intervention\n"
        + "  real :: mag_ctrl_early_amp     ! early/preconditioning magnetic command\n"
        + "  real :: mag_ctrl_aggressive_amp ! strongest bounded magnetic command\n"
        + "  real :: mag_ctrl_hold_amp      ! recovery/maintenance magnetic command\n"
        + "  real :: mag_ctrl_t_early       ! transition bias -> early\n"
        + "  real :: mag_ctrl_t_aggressive  ! transition early -> aggressive\n"
        + "  real :: mag_ctrl_t_hold        ! transition aggressive -> hold\n"
    )
    new = text[:match.start()] + addition + text[match.end():]
    return _write_if_changed(path, text, new)


def _install_input(path: Path) -> bool:
    text = _read(path)
    if '"imag_control_staged"' in text:
        return False
    # Insert directly after mag_ctrl_t_off registration. Match the two-line
    # add_var_double call without relying on the exact description text.
    pattern = re.compile(
        r'(\s*call\s+add_var_double\("mag_ctrl_t_off"\s*,\s*mag_ctrl_t_off\s*,\s*1\.e30\s*,\s*&\s*\n'
        r'\s*"[^"]*"\s*,\s*source_grp\)\s*\n)',
        re.I,
    )
    match = pattern.search(text)
    if not match:
        raise RuntimeError("mag_ctrl_t_off registration not found in input.f90")
    addition = match.group(1) + (
        '  call add_var_int("imag_control_staged", imag_control_staged, 0, &\n'
        '       "1: use scheduled bias/early/aggressive/hold magnetic command", source_grp)\n'
        '  call add_var_double("mag_ctrl_bias_amp", mag_ctrl_bias_amp, 0., &\n'
        '       "standing magnetic-control bias amplitude", source_grp)\n'
        '  call add_var_double("mag_ctrl_early_amp", mag_ctrl_early_amp, 0., &\n'
        '       "early magnetic-control amplitude", source_grp)\n'
        '  call add_var_double("mag_ctrl_aggressive_amp", mag_ctrl_aggressive_amp, 0., &\n'
        '       "aggressive magnetic-control amplitude", source_grp)\n'
        '  call add_var_double("mag_ctrl_hold_amp", mag_ctrl_hold_amp, 0., &\n'
        '       "hold magnetic-control amplitude", source_grp)\n'
        '  call add_var_double("mag_ctrl_t_early", mag_ctrl_t_early, 0., &\n'
        '       "time of bias-to-early transition", source_grp)\n'
        '  call add_var_double("mag_ctrl_t_aggressive", mag_ctrl_t_aggressive, 0., &\n'
        '       "time of early-to-aggressive transition", source_grp)\n'
        '  call add_var_double("mag_ctrl_t_hold", mag_ctrl_t_hold, 0., &\n'
        '       "time of aggressive-to-hold transition", source_grp)\n'
    )
    new = text[:match.start()] + addition + text[match.end():]
    return _write_if_changed(path, text, new)


def _install_ludef(path: Path) -> bool:
    text = _read(path)
    changed = False

    if not re.search(r"\bmag_cmd\b", text):
        decl = re.search(
            r"^(\s*real\s*::\s*mag_gate\s*,\s*mag_tau\s*,\s*mag_wr\s*,\s*mag_wz(?:\s*,\s*mag_phase)?)(\s*)$",
            text,
            re.M,
        )
        if not decl:
            raise RuntimeError("imag_control local declaration not found in ludef_t.f90")
        replacement = decl.group(1) + ", mag_cmd" + decl.group(2)
        text = text[:decl.start()] + replacement + text[decl.end():]
        changed = True

    marker = "! TCT_CONTROL_V2_STAGED_COMMAND"
    if marker not in text:
        old_if = "  if(imag_control.eq.1 .and. mag_ctrl_amp.ne.0.) then"
        pos = text.find(old_if)
        if pos < 0:
            # If another installer already converted the condition to mag_cmd,
            # refuse to guess rather than silently patch the wrong block.
            raise RuntimeError("imag_control source condition not found in ludef_t.f90")
        selector = f"""  {marker}\n  mag_cmd = mag_ctrl_amp\n  if(imag_control_staged.eq.1) then\n     if(time.lt.mag_ctrl_t_early) then\n        mag_cmd = mag_ctrl_bias_amp\n     else if(time.lt.mag_ctrl_t_aggressive) then\n        mag_cmd = mag_ctrl_early_amp\n     else if(time.lt.mag_ctrl_t_hold) then\n        mag_cmd = mag_ctrl_aggressive_amp\n     else if(time.lt.mag_ctrl_t_off) then\n        mag_cmd = mag_ctrl_hold_amp\n     else\n        mag_cmd = 0.\n     end if\n  end if\n\n  if(imag_control.eq.1 .and. mag_cmd.ne.0.) then"""
        text = text[:pos] + selector + text[pos + len(old_if):]

        amp_line = "temp79a(j) = mag_gate * mag_ctrl_amp * &"
        amp_pos = text.find(amp_line, pos)
        if amp_pos < 0:
            raise RuntimeError("imag_control amplitude application not found in ludef_t.f90")
        text = text[:amp_pos] + text[amp_pos:].replace(
            amp_line, "temp79a(j) = mag_gate * mag_cmd * &", 1
        )
        changed = True

    if changed:
        path.write_text(text, encoding="utf-8")
    return changed


def install() -> bool:
    modules = SRC / "unstructured/M3Dmodules.f90"
    inputf = SRC / "unstructured/input.f90"
    ludef = SRC / "unstructured/ludef_t.f90"
    changed = False
    changed |= _install_modules(modules)
    changed |= _install_input(inputf)
    changed |= _install_ludef(ludef)
    return changed


def build() -> None:
    if not BUILD.exists():
        raise FileNotFoundError(BUILD)
    p = subprocess.run(
        ["cmake", "--build", str(BUILD), "--target", "m3dc1_2d", "-j2"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    print(p.stdout, end="")
    if p.returncode:
        raise RuntimeError(f"M3D-C1 build failed with rc={p.returncode}")
    if not EXE.exists():
        raise RuntimeError(f"build completed but executable is missing: {EXE}")


def verify_source() -> None:
    checks = {
        SRC / "unstructured/M3Dmodules.f90": "imag_control_staged",
        SRC / "unstructured/input.f90": '"mag_ctrl_aggressive_amp"',
        SRC / "unstructured/ludef_t.f90": "TCT_CONTROL_V2_STAGED_COMMAND",
    }
    for path, needle in checks.items():
        if needle not in _read(path):
            raise RuntimeError(f"operator verification failed: {needle} missing from {path}")
    print("TCT Control V2 staged operator source verification: PASS")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["install", "build", "verify", "all"])
    args = ap.parse_args()
    if args.action in {"install", "all"}:
        changed = install()
        print("operator install:", "changed" if changed else "already installed")
    if args.action in {"build", "all"}:
        build()
    if args.action in {"verify", "all"}:
        verify_source()


if __name__ == "__main__":
    main()
