import re
from pathlib import Path
from typing import Union


def extract_energy_data(output_file):
    with open(output_file, "r") as file:
        content = file.read()

    # Regex to match the energy data section
    pattern = r"Root\s+Mult\.\s+Total Energy \(a.u.\)\s+Ex\. Energy \(a.u.\)\s+Ex\. Energy \(eV\)\s+Ex\. Energy \(nm\)\s+Osc\. \(a.u.\)\s+[-=]+\n((?:\s+\d+\s+\w+\s+[-+]?\d+\.\d+([ ]+[-+]?\d+\.\d+){0,5}\n?)+)"
    matches = re.findall(pattern, content)
    energy_data = []
    for match in matches:
        terms = match[0].strip().split()
        sublist = []
        for term in terms:
            if (
                term.isdigit() and sublist
            ):  # If the term is an integer and sublist is not empty
                energy_data.append(
                    [
                        float(x) if "." in x else int(x)
                        for x in sublist
                        if x not in ["singlet", "doublet"]
                    ]
                )  # Convert values to float or int, ignore non-numeric
                sublist = []  # Reset sublist for the next group
            sublist.append(term)  # Add the term to the current sublist
        if sublist:  # Append the last sublist if it exists
            energy_data.append(
                [
                    float(x) if "." in x else int(x)
                    for x in sublist
                    if x not in ["singlet", "doublet"]
                ]
            )  # Convert values to float or int, ignore non-numeric
    return energy_data


def get_uv_vis_data(file: Union[str, Path]):
    """
    Get the UV-Vis data from the energy data.
    """
    energy_data = extract_energy_data(file)
    uv_vis_data = []
    for excited_state in energy_data[1:]:
        uv_vis_data.append([excited_state[3], excited_state[5]])
    return uv_vis_data


if __name__ == "__main__":
    print(get_uv_vis_data("scratch/hhtda/x0000.out"))
