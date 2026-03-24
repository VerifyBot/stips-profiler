"""
Statistics — ASCII heatmaps and histograms for user activity visualization.

Computes hourly and monthly activity distributions from cached responses
and renders them as Rich-formatted strings for the TUI dashboard.
"""

from collections import Counter
from datetime import datetime
from typing import Any


# ---------------------------------------------------------------------------
# Color palettes for heatmap intensity
# ---------------------------------------------------------------------------
_HEAT_COLORS = [
    "dim",          # 0%
    "green",        # ~20%
    "yellow",       # ~40%
    "dark_orange",  # ~60%
    "red",          # ~80%
    "bold red",     # 100%
]

_BAR_CHAR = "█"
_BAR_HALF = "▌"
_EMPTY_CHAR = "░"


# ---------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------
def compute_hourly_distribution(responses: list[dict[str, Any]]) -> dict[int, int]:
    """
    Compute hourly activity distribution (0-23) from response timestamps.
    
    Returns: dict mapping hour (0-23) to count of responses in that hour.
    """
    hour_counts: Counter[int] = Counter()
    
    for resp in responses:
        time_str = resp.get("answer_time", resp.get("time", ""))
        if not time_str:
            continue
        try:
            # Format: "YYYY/MM/DD HH:MM:SS"
            dt = datetime.strptime(time_str, "%Y/%m/%d %H:%M:%S")
            hour_counts[dt.hour] += 1
        except (ValueError, AttributeError):
            continue
    
    # Fill in missing hours with 0
    return {h: hour_counts.get(h, 0) for h in range(24)}


def compute_monthly_distribution(responses: list[dict[str, Any]]) -> dict[str, int]:
    """
    Compute monthly activity distribution from response timestamps.
    
    Returns: dict mapping "YYYY-MM" to count of responses in that month,
             ordered chronologically.
    """
    month_counts: Counter[str] = Counter()
    
    for resp in responses:
        time_str = resp.get("answer_time", resp.get("time", ""))
        if not time_str:
            continue
        try:
            dt = datetime.strptime(time_str, "%Y/%m/%d %H:%M:%S")
            month_key = dt.strftime("%Y-%m")
            month_counts[month_key] += 1
        except (ValueError, AttributeError):
            continue
    
    # Sort chronologically
    return dict(sorted(month_counts.items()))


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def render_hourly_heatmap(hour_data: dict[int, int]) -> str:
    """
    Render a 24-hour activity heatmap as a Rich-formatted string.
    
    Uses colored blocks to represent intensity per hour.
    """
    if not hour_data or max(hour_data.values()) == 0:
        return "[dim]No activity data available[/dim]"
    
    max_count = max(hour_data.values())
    lines: list[str] = []
    
    lines.append("[bold cyan]🕐 Hourly Activity Heatmap[/bold cyan]")
    lines.append("")
    
    # Render as two rows of 12 hours each for readability
    for row_start in (0, 12):
        # Hour labels
        label_line = "  "
        block_line = "  "
        count_line = "  "
        
        for h in range(row_start, row_start + 12):
            count = hour_data.get(h, 0)
            intensity = count / max_count if max_count > 0 else 0
            color_idx = min(int(intensity * (len(_HEAT_COLORS) - 1)), len(_HEAT_COLORS) - 1)
            color = _HEAT_COLORS[color_idx]
            
            label_line += f"[dim]{h:02d}[/dim] "
            block_line += f"[{color}]{_BAR_CHAR}{_BAR_CHAR}[/{color}] "
            count_line += f"[dim]{count:>2}[/dim] "
        
        lines.append(label_line)
        lines.append(block_line)
        lines.append(count_line)
        lines.append("")
    
    # Legend
    total = sum(hour_data.values())
    peak_hour = max(hour_data, key=lambda h: hour_data.get(h, 0))
    lines.append(f"[dim]Total responses: {total:,} | Peak hour: {peak_hour:02d}:00[/dim]")
    
    return "\n".join(lines)


def render_monthly_histogram(month_data: dict[str, int]) -> str:
    """
    Render a monthly activity histogram as a Rich-formatted horizontal bar chart.
    """
    if not month_data or max(month_data.values()) == 0:
        return "[dim]No monthly data available[/dim]"
    
    max_count = max(month_data.values())
    max_bar_width = 30  # characters
    lines: list[str] = []
    
    lines.append("[bold cyan]📅 Monthly Activity Histogram[/bold cyan]")
    lines.append("")
    
    for month, count in month_data.items():
        # Display month as "Mar 2026"
        try:
            dt = datetime.strptime(month, "%Y-%m")
            label = dt.strftime("%b %Y")
        except ValueError:
            label = month
        
        bar_width = int((count / max_count) * max_bar_width) if max_count > 0 else 0
        empty_width = max_bar_width - bar_width
        
        # Color gradient based on intensity
        intensity = count / max_count if max_count > 0 else 0
        if intensity > 0.8:
            color = "bold green"
        elif intensity > 0.5:
            color = "green"
        elif intensity > 0.3:
            color = "yellow"
        else:
            color = "dim"
        
        bar = f"[{color}]{_BAR_CHAR * bar_width}[/{color}][dim]{_EMPTY_CHAR * empty_width}[/dim]"
        lines.append(f"  {label:>8}  {bar} {count:>4}")
    
    lines.append("")
    total = sum(month_data.values())
    active_months = len([v for v in month_data.values() if v > 0])
    avg = total // active_months if active_months > 0 else 0
    lines.append(f"[dim]Active months: {active_months} | Avg/month: {avg:,}[/dim]")
    
    return "\n".join(lines)
