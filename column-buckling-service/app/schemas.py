"""HTTP 请求/响应的数据模型（仅做形状解析，业务规则在 validation 层）。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# 上游可声明的一致单位制；声明后跳过 fy/E 量级合理性核查。
UnitSystem = Literal["SI", "MPA_MM", "CONSISTENT"]


class ColumnInput(BaseModel):
    """单根压杆的核算输入。

    所有力学量必须使用同一套自洽单位制（力与长度单位一致），
    例如统一用 N、mm、MPa(N/mm²)，或统一用 N、m、Pa。
    """

    model_config = ConfigDict(extra="forbid")

    # 杆长 L
    length: float
    # 截面惯性矩 I
    moment_of_inertia: float
    # 弹性模量 E
    elastic_modulus: float
    # 有效长度系数 K，缺省 1.0 即两端铰接
    effective_length_factor: float = Field(default=1.0)
    # 截面积 A
    area: float
    # 材料屈服强度 fy
    yield_strength: float
    # Perry 初始缺陷系数 alpha（无量纲），0 表示理想直杆
    imperfection: float = Field(default=0.0)
    # 单位制一致性声明；疑似 fy/E 量纲混用时必须显式声明
    unit_system: UnitSystem | None = Field(default=None)
