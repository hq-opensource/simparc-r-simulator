from typing import Any


def make_kpi_key(name: str, column: str, params: dict[str, Any]) -> str:
    """Construit une cle commune au moteur et aux loaders de KPI precalcules."""
    col_safe = column.replace(" ", "_")
    if not params:
        return f"{name}__{col_safe}"
    params_str = "__".join(f"{key}={value}" for key, value in sorted(params.items()))
    return f"{name}__{col_safe}__{params_str}"
