import os
import shutil
import subprocess
import tempfile

import pytest


def compile_verilog(verilog: str | None = None, filename: str | None = None, pkg_sv: str | None = None):
    """
    Compile Verilog with iverilog.

    Args:
        verilog: Verilog source string to compile.
        filename: Path to a Verilog file to compile (if verilog is None).
        pkg_sv: Optional package SV string to compile alongside the main source.

    Raises:
        AssertionError: If iverilog returns a non-zero exit code.
    """
    if not shutil.which("iverilog"):
        pytest.skip("iverilog not installed")

    if verilog is None and filename is None:
        raise ValueError("Must provide either verilog string or filename")

    if filename is not None:
        with open(filename) as f:
            verilog = f.read()

    tmpfiles = []
    try:
        # Write package file if provided
        pkg_tmp = None
        if pkg_sv is not None:
            pkg_tmp = tempfile.NamedTemporaryFile(suffix=".sv", mode="w", delete=False)
            pkg_tmp.write(pkg_sv)
            pkg_tmp.close()
            tmpfiles.append(pkg_tmp.name)

        # Write main source
        main_tmp = tempfile.NamedTemporaryFile(suffix=".v", mode="w", delete=False)
        main_tmp.write(verilog)
        main_tmp.close()
        tmpfiles.append(main_tmp.name)

        cmd = ["iverilog", "-g2012"]
        if pkg_tmp:
            cmd.append(pkg_tmp.name)
        cmd.append(main_tmp.name)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            output = (result.stdout + "\n" + result.stderr).strip()
            raise AssertionError(f"iverilog compilation failed:\n{output}")
    finally:
        for tf in tmpfiles:
            os.unlink(tf)


def simulate_verilog(dut_sv: str, tb_file: str, top: str = "tb") -> str:
    """
    Compile DUT + testbench with iverilog, run with vvp, return stdout.

    Args:
        dut_sv: DUT Verilog source string (emitted by plane).
        tb_file: Path to testbench .sv file.
        top: Top-level module name for vvp (default "tb").

    Returns:
        stdout from vvp execution.

    Raises:
        AssertionError: If iverilog compilation fails.
        subprocess.CalledProcessError: If vvp returns non-zero exit code.
    """
    if not shutil.which("iverilog") or not shutil.which("vvp"):
        pytest.skip("iverilog or vvp not installed")

    tmpfiles = []
    try:
        # Write DUT source
        dut_tmp = tempfile.NamedTemporaryFile(suffix=".v", mode="w", delete=False)
        dut_tmp.write(dut_sv)
        dut_tmp.close()
        tmpfiles.append(dut_tmp.name)

        # Compile
        sim_out = tempfile.NamedTemporaryFile(suffix=".out", mode="w", delete=False)
        sim_out.close()
        tmpfiles.append(sim_out.name)

        compile_cmd = ["iverilog", "-g2012", dut_tmp.name, tb_file, "-o", sim_out.name]
        compile_result = subprocess.run(
            compile_cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if compile_result.returncode != 0:
            output = (compile_result.stdout + "\n" + compile_result.stderr).strip()
            raise AssertionError(f"iverilog compilation failed:\n{output}")

        # Run simulation
        run_result = subprocess.run(
            ["vvp", sim_out.name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if run_result.returncode != 0:
            output = (run_result.stdout + "\n" + run_result.stderr).strip()
            raise AssertionError(f"vvp simulation failed:\n{output}")

        return run_result.stdout
    finally:
        for tf in tmpfiles:
            os.unlink(tf)
