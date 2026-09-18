"""请求/响应的 Pydantic 模型（输入校验的第一道关口）。

所有物理量必须为正的有限数值；缺陷系数允许为零（表示无缺陷，
未触及屈服时承载力回到欧拉临界力）。非数值、NaN、无穷一律拒绝。
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

UnitSystem = Literal["N-mm", "N-m", "kN-m", "kN-mm"]


class EulerInput(BaseModel):
    """欧拉临界力核算输入。"""

    model_config = ConfigDict(allow_inf_nan=False)

    length: float = Field(gt=0, description="杆长 L")
    moment_of_inertia: float = Field(gt=0, description="截面惯性矩 I")
    elastic_modulus: float = Field(gt=0, description="弹性模量 E")
    end_condition_factor: float = Field(gt=0, description="端部约束系数 K，两端铰接取 1")
    units: UnitSystem = Field(description="单位制声明，如 N-mm")
    label: Optional[str] = Field(default=None, description="可选的杆件标识")


class ColumnInput(EulerInput):
    """完整压杆稳定核算输入（含缺陷）。"""

    area: float = Field(gt=0, description="截面积 A")
    yield_strength: float = Field(gt=0, description="材料屈服强度 fy")
    imperfection_factor: float = Field(
        default=0.0, ge=0, description="初始缺陷系数 alpha，0 表示无缺陷"
    )


class BatchInput(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    columns: List[ColumnInput] = Field(min_length=1, description="批量核算的压杆列表")


class EulerResult(BaseModel):
    effective_length: float
    euler_critical_load: float
    units: UnitSystem
    label: Optional[str] = None


class CapacityResult(EulerResult):
    area: float
    radius_of_gyration: float
    slenderness_ratio: float
    yield_load: float
    relative_slenderness: float
    imperfection_factor: float
    imperfection_amplification: float
    capacity: float
    governing_mode: str
    capacity_to_euler_ratio: float


class BatchItemResult(BaseModel):
    index: int
    label: Optional[str] = None
    status: Literal["success", "error"]
    result: Optional[CapacityResult] = None
    error: Optional[str] = None


class BatchResult(BaseModel):
    total: int
    succeeded: int
    failed: int
    items: List[BatchItemResult]
