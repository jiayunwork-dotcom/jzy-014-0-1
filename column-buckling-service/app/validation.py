"""输入校验：把任意上游输入转成干净的 ColumnInput，或给出可读错误。

校验顺序固定：
1. 形状/类型（缺字段、非数值、多余字段）
2. 有限性（NaN / inf / -inf 一律拒绝）
3. 正值（L、I、E、K、A、fy 必须为正；K 非正或 L 非正在计算前拒绝）
4. 缺陷系数非负
5. fy/E 量纲混用核查（未声明一致单位制且量级可疑时拒绝）

长细比为零、A 非正导致回转半径不可定义，也在此层提前拒绝。
"""

import math
from typing import Any

from pydantic import ValidationError

from app.errors import ServiceError
from app.schemas import ColumnInput

# 必须严格为正的标量字段：(字段名, 中文名)
_POSITIVE_FIELDS: tuple[tuple[str, str], ...] = (
    ("length", "杆长"),
    ("moment_of_inertia", "截面惯性矩"),
    ("elastic_modulus", "弹性模量"),
    ("effective_length_factor", "端部约束系数K"),
    ("area", "截面积"),
    ("yield_strength", "材料屈服强度"),
)

# 未声明单位制时 fy/E 的可疑区间。任何真实结构材料（钢/铝/混凝土/木材）的
# fy/E 都落在约 1e-4 ~ 5e-3；越界几乎必然是屈服强度与弹性模量单位/量纲混用
# （MPa 与 Pa 相差 1e6，混填会让比值掉到 1e-9 或飙到 1e3 量级）。
SUSPECT_FY_OVER_E_HIGH = 0.1
SUSPECT_FY_OVER_E_LOW = 1e-5

_STOCKY_LIMIT = 0.2  # 与 domain.perry 的短柱门槛保持一致


def _fail(
    code: str,
    message: str,
    field: str | None = None,
    *,
    index: int | None = None,
    status_code: int = 422,
) -> ServiceError:
    """构造带批量组号前缀的可读错误。index 为 0 基，对外显示从第 1 组起。"""
    prefix = f"第{index + 1}组：" if index is not None else ""
    return ServiceError(
        code=code,
        message=prefix + message,
        field=field,
        status_code=status_code,
        details={"batch_index": index} if index is not None else None,
    )


def parse_column_input(
    raw: Any, *, index: int | None = None
) -> ColumnInput:
    """解析并校验单组压杆输入；非法时抛 ServiceError（可读、不崩溃）。"""
    if not isinstance(raw, dict):
        raise _fail(
            "INVALID_ITEM",
            "每组核算参数必须是一个包含各字段的对象",
            index=index,
        )

    data = _parse_shape(raw, index=index)
    _check_finite(data, index=index)
    _check_positive(data, index=index)
    _check_imperfection(data, index=index)
    _check_units_and_slenderness(data, index=index)
    return data


def _parse_shape(raw: dict[str, Any], *, index: int | None) -> ColumnInput:
    try:
        return ColumnInput.model_validate(raw)
    except ValidationError as exc:
        err = exc.errors()[0]
        loc = err.get("loc") or ()
        field = str(loc[-1]) if loc else None
        etype = err.get("type", "")
        label = _field_label(field) if field else "输入"

        if etype == "missing":
            raise _fail(
                "MISSING_FIELD",
                f"缺少必填字段 {field}（{label}）",
                field,
                index=index,
            )
        if etype == "extra_forbidden":
            raise _fail(
                "EXTRA_FIELD",
                f"存在不被接受的多余字段 {field}，请核对参数名",
                field,
                index=index,
            )
        if etype in (
            "float_parsing",
            "int_parsing",
            "float_type",
            "int_type",
            "bool_type",
            "dict_type",
            "literal_error",
        ):
            raise _fail(
                "INVALID_NUMBER",
                f"字段 {field}（{label}）取值非法：必须是有限数值",
                field,
                index=index,
            )
        # 其它形状类错误统一给出可读说明。
        raise _fail(
            "INVALID_VALUE",
            f"字段 {field}（{label}）不合法：{err.get('msg', '取值错误')}",
            field,
            index=index,
        )


def _check_finite(data: ColumnInput, *, index: int | None) -> None:
    values = {
        "length": data.length,
        "moment_of_inertia": data.moment_of_inertia,
        "elastic_modulus": data.elastic_modulus,
        "effective_length_factor": data.effective_length_factor,
        "area": data.area,
        "yield_strength": data.yield_strength,
        "imperfection": data.imperfection,
    }
    for field, value in values.items():
        if not math.isfinite(value):
            raise _fail(
                "NON_FINITE_VALUE",
                f"字段 {field}（{_field_label(field)}）必须是有限数值，"
                "不接受 NaN 或无穷大",
                field,
                index=index,
            )


def _check_positive(data: ColumnInput, *, index: int | None) -> None:
    for field, label in _POSITIVE_FIELDS:
        value = getattr(data, field)
        if value <= 0:
            if field == "effective_length_factor":
                hint = "约束系数K必须为正；两端铰接请显式取 K=1"
            elif field == "length":
                hint = "杆长必须为正，非正杆长在计算前拒绝"
            elif field == "area":
                hint = "截面积必须为正，否则回转半径无法定义、长细比无法计算"
            else:
                hint = f"{label}必须为正"
            raise _fail(
                "NON_POSITIVE_VALUE",
                f"字段 {field}（{label}）={_fmt(value)} 非法：{hint}",
                field,
                index=index,
            )


def _check_imperfection(data: ColumnInput, *, index: int | None) -> None:
    if data.imperfection < 0:
        raise _fail(
            "NEGATIVE_IMPERFECTION",
            f"初始缺陷系数 imperfection={_fmt(data.imperfection)} 非法："
            "缺陷系数不得为负，理想直杆请取 0",
            "imperfection",
            index=index,
        )


def _check_units_and_slenderness(
    data: ColumnInput, *, index: int | None
) -> None:
    # 量纲混用核查：未声明一致单位制，且 fy/E 偏离任何真实结构材料的量级。
    if data.unit_system is None:
        ratio = data.yield_strength / data.elastic_modulus
        if ratio > SUSPECT_FY_OVER_E_HIGH or ratio < SUSPECT_FY_OVER_E_LOW:
            raise _fail(
                "UNIT_MISMATCH_SUSPECTED",
                f"屈服强度/弹性模量 = {ratio:.4g}，超出真实结构材料的合理区间"
                f" [{SUSPECT_FY_OVER_E_LOW:g}, {SUSPECT_FY_OVER_E_HIGH:g}]，"
                "疑似屈服强度与弹性模量量纲/单位混用"
                "（例如一个填 MPa、另一个填 Pa）。请确认二者使用同一套自洽单位制，"
                "并通过 unit_system 字段声明（SI / MPA_MM / CONSISTENT）后重试",
                "yield_strength",
                index=index,
            )

    # 几何上的长细比必须可定义且为正。
    radius = math.sqrt(data.moment_of_inertia / data.area)
    slenderness = data.effective_length_factor * data.length / radius
    if slenderness <= 0:
        raise _fail(
            "INVALID_SLENDERNESS",
            "长细比必须为正（有效长度须为正、回转半径须可定义）",
            "length",
            index=index,
        )


def _field_label(field: str | None) -> str:
    for name, label in _POSITIVE_FIELDS:
        if name == field:
            return label
    return {
        "imperfection": "初始缺陷系数",
        "unit_system": "单位制声明",
    }.get(field or "", field or "输入")


def _fmt(value: float) -> str:
    try:
        return f"{value:.6g}"
    except Exception:  # noqa: BLE001 - 任何格式化失败都不应影响报错
        return str(value)
