#!/usr/bin/env python3
"""Repair wrapper for the uninterrupted native two-window TCT audit.

The first two-window installer used a loose regex around the cd_t_off input
registration. On this M3D-C1 checkout that regex could consume the first line
of the following continued add_var_* call, leaving the newly inserted J_0cd2
registrations inside that call and breaking input.f90.

This wrapper repairs an already-touched source tree and installs the second
window registrations only after the complete cd_t_off add_var_double call.
It then delegates to native_two_window_sustained_refinement_audit.py.
"""
from __future__ import annotations

import re

import native_two_window_sustained_refinement_audit as audit


SECOND_REGS = (
    '  call add_var_double("J_0cd2", J_0cd2, 0., &\n'
    '       "second-window current-drive amplitude", source_grp)\n'
    '  call add_var_double("cd_t2_on", cd_t2_on, 1.e30, &\n'
    '       "second current-drive turn-on time", source_grp)\n'
    '  call add_var_double("cd_t2_off", cd_t2_off, 1.e30, &\n'
    '       "second current-drive turn-off time", source_grp)\n'
)


def install_input_registrations_safely() -> bool:
    """Repair/reinstall second-window input variables at a complete-call anchor."""
    inputf = audit.SRC / "unstructured/input.f90"
    if not inputf.exists():
        raise FileNotFoundError(inputf)

    text = inputf.read_text()
    before = text

    # Remove the exact two-line registration calls from the previous installer
    # wherever they landed. If they were inserted inside the next continued
    # call, removing them makes that original call contiguous again.
    for var in ("J_0cd2", "cd_t2_on", "cd_t2_off"):
        pattern = re.compile(
            rf'(?mi)^[ \t]*call[ \t]+add_var_double\("{re.escape(var)}"'
            rf'[^\n]*&[ \t]*\n[ \t]*[^\n]*source_grp\)[ \t]*\n?'
        )
        text, _ = pattern.subn("", text)

    # Match the COMPLETE cd_t_off registration, stopping at its source_grp)
    # continuation line. This deliberately cannot consume the next call.
    anchor = re.search(
        r'(?mi)^[ \t]*call[ \t]+add_var_double\("cd_t_off"'
        r'[^\n]*&[ \t]*\n[ \t]*[^\n]*source_grp\)[ \t]*$',
        text,
    )
    if not anchor:
        raise RuntimeError(
            "complete cd_t_off input registration anchor not found after repair"
        )

    insert_at = anchor.end()
    text = text[:insert_at] + "\n" + SECOND_REGS.rstrip("\n") + text[insert_at:]

    # Structural guards: each new input variable must be registered exactly
    # once and the insertion must follow a completed call, never an '&' line.
    for var in ("J_0cd2", "cd_t2_on", "cd_t2_off"):
        count = len(
            re.findall(
                rf'(?mi)^[ \t]*call[ \t]+add_var_double\("{re.escape(var)}"',
                text,
            )
        )
        if count != 1:
            raise RuntimeError(f"{var} registration count is {count}, expected 1")

    jpos = text.find('call add_var_double("J_0cd2"')
    previous_line = text[:jpos].rstrip().splitlines()[-1]
    if previous_line.rstrip().endswith("&"):
        raise RuntimeError(
            "J_0cd2 would be inserted inside a continued Fortran call; refusing"
        )
    if "source_grp)" not in previous_line:
        raise RuntimeError(
            "J_0cd2 is not immediately after the completed cd_t_off registration"
        )

    if text != before:
        inputf.write_text(text)
        return True
    return False


_original_install = audit.install_native_two_window_operator


def repaired_install_native_two_window_operator() -> bool:
    # Ensure the validated source=4 base operator and cd_t_off registration exist.
    base_changed = audit.nfc.install_current_redistribution_operator()

    # Repair a source tree left malformed by the first installer, or install
    # the second-window input variables correctly on a clean tree.
    input_changed = install_input_registrations_safely()

    # Delegate module declarations and transport-gate installation. Because
    # J_0cd2 now already exists in input.f90, the old loose input regex is
    # bypassed.
    native_changed = _original_install()
    return bool(base_changed or input_changed or native_changed)


audit.install_native_two_window_operator = repaired_install_native_two_window_operator


if __name__ == "__main__":
    raise SystemExit(audit.main())
