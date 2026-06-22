"""Tiny inline HTML/CSS visual helpers — avoids pulling matplotlib into Pyodide."""
from __future__ import annotations

from shiny import ui


def hbar(label: str, value: float, vmax: float, *, suffix: str = "", color: str = "#1f6feb") -> str:
    """One horizontal bar row as an HTML string."""
    pct = 0 if not vmax else max(0.0, min(100.0, 100.0 * value / vmax))
    return (
        f'<div class="hbar-row"><span class="hbar-label">{label}</span>'
        f'<span class="hbar-track"><span class="hbar-fill" style="width:{pct:.1f}%;'
        f'background:{color}"></span></span>'
        f'<span class="hbar-val">{value:g}{suffix}</span></div>'
    )


def bars(pairs: list[tuple[str, float]], *, suffix: str = "", color: str = "#1f6feb") -> ui.HTML:
    vmax = max((v for _, v in pairs), default=0)
    return ui.HTML('<div class="hbar">' + "".join(
        hbar(lbl, v, vmax, suffix=suffix, color=color) for lbl, v in pairs
    ) + "</div>")


def stat_card(label: str, value: str, sub: str = "") -> ui.Tag:
    return ui.div(
        ui.div(value, class_="stat-value"),
        ui.div(label, class_="stat-label"),
        ui.div(sub, class_="stat-sub") if sub else None,
        class_="stat-card",
    )
