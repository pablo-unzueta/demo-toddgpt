from src.toddgpt.tools.chemcloud_tool import FindJobExample, RunTerachem
from src.toddgpt.tools.datatypes import AtomsDict
import pytest
from pathlib import Path

hf_input = """run energy
basis sto-3g
method hf
coordinates geom.xyz
charge 0"""

wpbe_input = """basis aug-cc-pvdz
method wpbe
rc_w 0.3
charge 0
spinmult 1
maxit 100
run energy
coordinates geom.xyz
purify no
cis yes
cisnumstates 10
cismult 1
cisguessvecs 30
cismax 300
cismaxiter 500
cisalgorithm davidson
cisconvtol 1e-5
fmsmult 1
cpcisiter 100
cpcistol 1e-5
scf diis
maxit 1000
precision mixed"""

frequency_input = """run          initcond
basis        def2-svp
method       wb97xd3
charge       0
spinmult     1

coordinates  geom.xyz"""


cb_atoms_dict = AtomsDict(
    numbers=[6, 6, 6, 1, 1, 6, 8, 1, 1, 1, 1],
    positions=[
        [0.0440612014, 0.0000001558, -1.5465977201],
        [-0.0504691669, -1.1047385423, -0.4620580772],
        [-0.0000317499, -0.0000001515, 0.5956577117],
        [0.7674364582, -1.8394959152, -0.4054712947],
        [-1.0066462627, -1.6522501660, -0.4396105229],
        [-0.0504694183, 1.1047385161, -0.4620577727],
        [0.0857549810, -0.0000002994, 1.7874130704],
        [0.7674360397, 1.8394960616, -0.4054707664],
        [-1.0066466608, 1.6522498808, -0.4396100549],
        [-0.7635861985, 0.0000001630, -2.2912019884],
        [1.0052007567, 0.0000003230, -2.0798180724],
    ],
)


@pytest.mark.parametrize(
    "job_name, expected",
    [
        ("initcond", frequency_input.strip()),  # Strip here
        ("nonexistent", "No example input found for job nonexistent"),
    ],
)
def test_find_job_example(job_name, expected):
    tool = FindJobExample()
    if job_name == "nonexistent":
        with pytest.raises(ValueError, match=expected):
            tool.find_job_example(job_name)
    else:
        result = tool.find_job_example(job_name)
        assert result.strip() == expected  # Strip only the actual output


@pytest.mark.parametrize(
    "tc_input, atoms_dict, output_dir",
    [(hf_input.strip(), cb_atoms_dict, "./scratch")],
)
def test_run_terachem(tc_input, atoms_dict, output_dir):
    path = Path(output_dir)
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    tool = RunTerachem()
    prog_output = tool._run(tc_input=tc_input, atoms_dict=atoms_dict)
    with open(path / "tc.out", "w") as f:
        f.write(prog_output.stdout)
    prog_output.results.save_files(output_dir)
    assert prog_output.success
