from src.toddgpt.tools.spectra import GenerateSpectrum
from src.toddgpt.tools.chemcloud_tool import RunTerachem, FindJobExample
from src.toddgpt.tools.datatypes import AtomsDict
import pytest
from pathlib import Path

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


@pytest.mark.parametrize("atoms_dict", [cb_atoms_dict])
def test_generate_spectrum(atoms_dict):
    tool = GenerateSpectrum()
    tool._run(atoms_dict)


@pytest.mark.parametrize("atoms_dict", [cb_atoms_dict])
def test_run_td_dft(atoms_dict):
    tool = GenerateSpectrum()
    tool._run(atoms_dict, "hhtda")


def test_plot_spectra():
    tool = GenerateSpectrum()
    tool.plot_spectra(Path("./scratch/spectra/hhtda"))
