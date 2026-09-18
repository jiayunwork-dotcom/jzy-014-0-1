"""元信息接口：Perry 折减约定/容差配置回显、预置算例。"""

from fastapi import APIRouter

from app import __version__
from app.config import settings
from app.domain.euler import PI_SQUARED
from app.domain.perry import (
    DEFAULT_RELATIVE_TOLERANCE,
    STOCKY_SLENDERNESS_LIMIT,
)
from app.examples import PRESET_EXAMPLE, preset_reference_euler
from app.service import compute_full
from app.validation import (
    SUSPECT_FY_OVER_E_HIGH,
    SUSPECT_FY_OVER_E_LOW,
    parse_column_input,
)

router = APIRouter(tags=["meta"])


@router.get("/convention")
async def get_convention() -> dict:
    """回显钉死的 Perry 折减约定、公式、控制模式规则与容差配置。"""
    return {
        "formulas": {
            "effective_length": "Le = K * L  （两端铰接 K=1）",
            "euler_critical_force": "Fe = pi^2 * E * I / Le^2",
            "radius_of_gyration": "r = sqrt(I / A)",
            "slenderness_ratio": "lambda = Le / r",
            "yield_force": "Ny = fy * A",
            "normalized_slenderness": "lambda_bar = sqrt(Ny / Fe)",
            "perry_eta": "eta = alpha * max(0, lambda_bar - 0.2)",
            "perry_phi": "phi = 0.5 * (1 + eta + lambda_bar^2)",
            "perry_reduction_factor": "chi = 1 / (phi + sqrt(phi^2 - lambda_bar^2))",
            "capacity": "Nr = chi * Ny",
        },
        "constants": {
            "pi": PI_SQUARED ** 0.5,
            "pi_squared": PI_SQUARED,
            "stocky_slenderness_limit": STOCKY_SLENDERNESS_LIMIT,
            "pinned_effective_length_factor": 1.0,
            "imperfection_factor_min": 0.0,
        },
        "control_modes": [
            {
                "mode": "yield",
                "label": "材料屈服控制",
                "rule": (
                    f"lambda_bar <= {STOCKY_SLENDERNESS_LIMIT}（短柱）"
                    "或承载力触及屈服上限 Ny；Nr=Ny"
                ),
            },
            {
                "mode": "euler",
                "label": "欧拉屈曲控制",
                "rule": "缺陷为零且未触及屈服（长柱），或结果贴合欧拉上限 Fe；Nr=Fe",
            },
            {
                "mode": "perry",
                "label": "初始缺陷折减控制（Perry）",
                "rule": "缺陷 alpha>0 且处于弹塑性过渡区，Nr=chi·Ny，低于 Fe 且低于 Ny",
            },
        ],
        "guaranteed_behaviors": [
            "铰接 K=1 时 Fe 严格等于 pi^2 E I / L^2",
            "只把杆长加倍，Fe 变为 1/4；K 从 1 改到 2，Fe 变为 1/4",
            "I 加倍 Fe 加倍，E 加倍 Fe 加倍",
            "缺陷系数为零且未触及屈服时，承载力回到 Fe",
            "短柱承载力不超过屈服力 Ny，绝不把欧拉力直接当成短柱承载力",
            "缺陷越大、长细比越大，折减后承载力越低",
        ],
        "tolerance": {
            "relative_tolerance": settings.relative_tolerance,
            "default_relative_tolerance": DEFAULT_RELATIVE_TOLERANCE,
            "usage": "控制模式归类（贴合屈服/欧拉）使用的相对比较容差",
        },
        "validation": {
            "required_positive": [
                "length",
                "moment_of_inertia",
                "elastic_modulus",
                "effective_length_factor",
                "area",
                "yield_strength",
            ],
            "imperfection_non_negative": True,
            "finite_only": "NaN、+inf、-inf 一律拒绝",
            "fy_over_e_suspect_range": [
                SUSPECT_FY_OVER_E_LOW,
                SUSPECT_FY_OVER_E_HIGH,
            ],
            "unit_policy": (
                "未通过 unit_system 声明一致单位制时，若 fy/E 超出"
                f" [{SUSPECT_FY_OVER_E_LOW:g}, {SUSPECT_FY_OVER_E_HIGH:g}]"
                " 将判为屈服强度与弹性模量量纲混用并拒绝；"
                "可声明 SI / MPA_MM / CONSISTENT 表示二者同属一套自洽单位制"
            ),
        },
        "batch": {"max_items": settings.max_batch_items},
        "version": __version__,
    }


@router.get("/example")
async def get_example() -> dict:
    """预置算例：两端铰接、常见工字型量级截面（可直接照抄调用）。"""
    data = parse_column_input(PRESET_EXAMPLE["input"])
    result = compute_full(data, relative_tolerance=settings.relative_tolerance)
    reference = preset_reference_euler()
    return {
        "name": PRESET_EXAMPLE["name"],
        "description": PRESET_EXAMPLE["description"],
        "request": PRESET_EXAMPLE["input"],
        "reference_euler": reference,
        "result": result,
        "checks": {
            "k_equals_1_matches_formula": abs(
                result["euler_critical_force"] - reference["euler_critical_force"]
            )
            < settings.relative_tolerance * reference["euler_critical_force"],
        },
    }
