import re
from pathlib import Path
from typing import Union

def extract_energy_data(output_file):
    with open(output_file, "r") as file:
        content = file.read()

        pattern = r"Final Excited State Results:\n\n\s*Root\s+Total Energy \(a.u.\)\s+Ex\. Energy \(eV\)\s+Osc\. \(a.u.\)\s+< S\^2 >\s+Max CI Coeff\.\s+Excitation\n-+\n((?:\s+\d+\s+[-+]?\d+\.\d+\s+[-+]?\d+\.\d+\s+[-+]?\d+\.\d+\s+[-+]?\d+\.\d+\s+[-+]?\d+\.\d+\s+\d+\s+->\s+\d+\s+:\s+\w+\s+->\s+\w+\n?)+)"
        matches = re.findall(pattern, content)
        excited_state_data = []
        for match in matches:
            terms = match.strip().splitlines()
            for term in terms:
                values = term.split()
                excited_state_data.append({
                    "root": int(values[0]),
                    "total_energy": float(values[1]),
                    "ex_energy_eV": float(values[2]),
                    "oscillator_strength": float(values[3]),
                    "squared_spin": float(values[4]),
                    "max_ci_coeff": float(values[5]),
                    "excitation": values[6:]
                })
        return excited_state_data

def get_uv_vis_data(file: Union[str, Path]):
    """
    Get the UV-Vis data from the energy data.
    """
    energy_data = extract_energy_data(file)
    uv_vis_data = []
    for excited_state in energy_data:
        uv_vis_data.append([excited_state["ex_energy_eV"], excited_state["oscillator_strength"]])
    return uv_vis_data


if __name__ == "__main__":
    print(get_uv_vis_data("scratch/wpbe/x0000.out"))
