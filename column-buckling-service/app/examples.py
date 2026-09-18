"""预置算例：两端铰接、常见工字型量级截面。

单位制（自洽，MPa = N/mm²）：
    L = 6000 mm，I = 2.0e8 mm^4，A = 7000 mm²，
    E = 2.05e5 MPa(N/mm²)，fy = 345 MPa，K = 1.0（铰接）

理想直杆（imperfection=0）时：
    Fe = pi^2 * E * I / L^2       （K=1 严格对上该式）
    本例 lambda_bar < 1，短柱，承载力由屈服封顶为 fy*A；
    接口同时回显参考欧拉临界力与 Perry 折减后的承载力。
"""

import math

PRESET_EXAMPLE = {
    "name": "pinned_i_section_column",
    "description": "两端铰接常见工字型量级截面压杆（单位 N、mm、MPa）",
    "input": {
        "length": 6000.0,
        "moment_of_inertia": 2.0e8,
        "elastic_modulus": 2.05e5,
        "effective_length_factor": 1.0,
        "area": 7000.0,
        "yield_strength": 345.0,
        "imperfection": 0.0,
        "unit_system": "MPA_MM",
    },
}


def preset_reference_euler() -> dict:
    """算例的参考欧拉临界力，按 π²EI/L²（K=1）直接给出。"""
    inp = PRESET_EXAMPLE["input"]
    fe = (
        math.pi ** 2
        * inp["elastic_modulus"]
        * inp["moment_of_inertia"]
        / inp["length"] ** 2
    )
    return {"formula": "pi^2 * E * I / L^2  (K=1)", "euler_critical_force": fe}
