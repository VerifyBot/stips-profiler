"""
Interactive Dashboard — Textual-based TUI for browsing the user profile tree.

Screen 5:
  Left panel:  Navigable tree of categories → sub-categories → facts
  Right panel: Dynamic detail view with AI summary + Hebrew source quotes

Screen 6 (Footer):
  [E]xport to JSON | [C]lear Cache | [Q]uit
"""

import json
from pathlib import Path
from typing import Any, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Footer,
    Header,
    Static,
    Tree,
)
from textual.widgets.tree import TreeNode

from src.ui.cli_flow import fix_bidi
from src.ui.stats import (
    compute_hourly_distribution,
    compute_monthly_distribution,
    render_hourly_heatmap,
    render_monthly_histogram,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _build_tree_data(profile_dict: dict[str, Any]) -> dict[str, Any]:
    """Ensure profile dict is in the right shape for tree building."""
    return profile_dict


# ---------------------------------------------------------------------------
# The Dashboard App
# ---------------------------------------------------------------------------
class ProfileDashboard(App):
    """
    Full-screen interactive Textual TUI for viewing the profiling results.

    Args:
        profile_data: The display dict from UserProfileTree.to_display_dict()
        user_id:      The Stips user ID (for export naming)
        nickname:     The user's Stips nickname
        responses:    List of raw response dicts (for statistics)
    """

    TITLE = "Stips Profiler — Dashboard"

    CSS = """
    Screen {
        layout: horizontal;
    }

    #tree-panel {
        width: 45%;
        dock: left;
        border: solid $accent;
        padding: 1 2 3 2;
        overflow-y: auto;
    }

    #detail-panel {
        width: 55%;
        dock: right;
        border: solid $secondary;
        padding: 1 2 3 2;
        overflow-y: auto;
        text-align: right;
        content-align: right top;
    }

    #detail-title {
        text-style: bold;
        color: $text;
        margin-bottom: 1;
    }

    #detail-summary {
        color: $text-muted;
        margin-bottom: 1;
    }

    #detail-facts {
        color: $text;
    }

    Footer {
        dock: bottom;
    }

    Header {
        dock: top;
    }
    """

    BINDINGS = [
        Binding("e", "export_json", "Export to JSON"),
        Binding("c", "clear_cache", "Clear Cache"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        profile_data: dict[str, Any],
        user_id: int,
        nickname: str,
        cache_clear_callback: Optional[object] = None,
        responses: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._profile_data = _build_tree_data(profile_data)
        self._user_id = user_id
        self._nickname = nickname
        self._cache_clear_callback = cache_clear_callback
        self._responses = responses or []
        # Store a mapping from tree node to its detail data
        self._node_details: dict[int, dict[str, Any]] = {}
        # Pre-compute statistics
        self._hourly_data = compute_hourly_distribution(self._responses)
        self._monthly_data = compute_monthly_distribution(self._responses)

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="tree-panel"):
                yield Tree(f"📋 Profile: @{fix_bidi(self._nickname)}", id="profile-tree")
            with Vertical(id="detail-panel"):
                yield Static(
                    "[bold]Select a category from the tree[/bold]",
                    id="detail-title",
                )
                yield Static("", id="detail-summary")
                yield Static("", id="detail-facts")
        yield Footer()

    def on_mount(self) -> None:
        """Build the tree structure from profile data."""
        tree: Tree = self.query_one("#profile-tree", Tree)  # type: ignore[assignment]
        tree.root.expand()

        # --- Statistics node ---
        stats_node = tree.root.add("📊 General Statistics", expand=False)
        hourly_node = stats_node.add_leaf("🕐 Hourly Activity Heatmap")
        self._node_details[id(hourly_node)] = {
            "type": "stats_hourly",
        }
        monthly_node = stats_node.add_leaf("📅 Monthly Activity Histogram")
        self._node_details[id(monthly_node)] = {
            "type": "stats_monthly",
        }
        # Stats overview
        self._node_details[id(stats_node)] = {
            "type": "stats_overview",
        }

        # --- Profile categories ---
        for trunk_label, sub_categories in self._profile_data.items():
            trunk_node = tree.root.add(trunk_label, expand=False)

            if not isinstance(sub_categories, dict):
                continue

            for sub_label, facts_list in sub_categories.items():
                sub_node = trunk_node.add(fix_bidi(sub_label))

                if not isinstance(facts_list, list):
                    continue

                # Store detail data for this sub-category node
                self._node_details[id(sub_node)] = {
                    "label": sub_label,
                    "facts": facts_list,
                    "parent": trunk_label,
                }

                for fact_item in facts_list:
                    if isinstance(fact_item, dict):
                        fact_text = fact_item.get("fact", "")
                        leaf = sub_node.add_leaf(f"• {fix_bidi(fact_text)}")
                        self._node_details[id(leaf)] = {
                            "label": fact_text,
                            "fact": fact_item,
                            "parent": sub_label,
                        }

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        """Update the right panel when a tree node is highlighted."""
        node = event.node
        detail = self._node_details.get(id(node))

        title_widget: Static = self.query_one("#detail-title", Static)  # type: ignore[assignment]
        summary_widget: Static = self.query_one("#detail-summary", Static)  # type: ignore[assignment]
        facts_widget: Static = self.query_one("#detail-facts", Static)  # type: ignore[assignment]

        # --- Handle statistics nodes ---
        if detail and detail.get("type") == "stats_overview":
            title_widget.update("[bold]📊 General Statistics[/bold]")
            summary_widget.update(
                f"[dim]Activity analysis from {len(self._responses):,} responses[/dim]"
            )
            # Show both heatmap and histogram
            hourly_text = render_hourly_heatmap(self._hourly_data)
            monthly_text = render_monthly_histogram(self._monthly_data)
            facts_widget.update(f"{hourly_text}\n\n{monthly_text}")
            return

        if detail and detail.get("type") == "stats_hourly":
            title_widget.update("[bold]🕐 Hourly Activity Heatmap[/bold]")
            summary_widget.update(
                "[dim]Distribution of responses across hours of the day[/dim]"
            )
            facts_widget.update(render_hourly_heatmap(self._hourly_data) + "\n")
            return

        if detail and detail.get("type") == "stats_monthly":
            title_widget.update("[bold]📅 Monthly Activity Histogram[/bold]")
            summary_widget.update(
                "[dim]Number of responses per month[/dim]"
            )
            facts_widget.update(render_monthly_histogram(self._monthly_data) + "\n")
            return

        # --- Handle profile nodes ---
        if detail is None:
            # Trunk-level node — show high-level info
            label = str(node.label)
            trunk_data = self._profile_data.get(label, {})
            if isinstance(trunk_data, dict):
                total = sum(
                    len(v) for v in trunk_data.values() if isinstance(v, list)
                )
                title_widget.update(f"[bold]{label}[/bold]")
                summary_widget.update(
                    f"[dim]{len(trunk_data)} sub-categories, {total} total facts[/dim]"
                )
                facts_widget.update("")
            else:
                title_widget.update(f"[bold]{label}[/bold]")
                summary_widget.update("")
                facts_widget.update("")
            return

        facts_list = detail.get("facts")
        single_fact = detail.get("fact")

        if single_fact:
            # Leaf-level: show individual fact with source + reference
            title_widget.update(
                f"[bold]📌 {fix_bidi(single_fact.get('fact', ''))}[/bold]"
            )
            source = single_fact.get("source_quote", "")
            question_id = single_fact.get("question_id")
            answer_date = single_fact.get("answer_date", "")

            summary_parts = [f"[dim]Sub-category: {fix_bidi(detail.get('parent', ''))}[/dim]"]
            if answer_date:
                summary_parts.append(f"[dim]{answer_date}[/dim]")
            summary_widget.update(" | ".join(summary_parts))

            lines: list[str] = []
            display_source = fix_bidi(source)

            # Clickable link icon next to quote
            if question_id:
                url = f"https://stips.co.il/ask/{question_id}"
                lines.append(
                    f"\n[bold cyan]Source Evidence:[/bold cyan]\n"
                    f'  [@click=app.copy_link("{url}")]🔗[/] [italic]"{display_source}"[/italic]'
                )
            else:
                lines.append(
                    f"\n[bold cyan]Source Evidence:[/bold cyan]\n"
                    f'  [italic]"{display_source}"[/italic]'
                )

            facts_widget.update("\n".join(lines) + "\n")

        elif facts_list:
            # Sub-category level: show all facts with sources
            parent = detail.get("parent", "")
            label = detail.get("label", "")
            title_widget.update(f"[bold]📂 {fix_bidi(label)}[/bold]")
            summary_widget.update(f"[dim]Category: {fix_bidi(parent)}[/dim]")

            lines: list[str] = []
            lines.append("")
            lines.append("[bold cyan]Source Evidence:[/bold cyan]")
            for i, f in enumerate(facts_list, 1):
                if isinstance(f, dict):
                    fact_text = fix_bidi(f.get("fact", ""))
                    answer_date = f.get("answer_date", "")
                    question_id = f.get("question_id")

                    # Fact header with date
                    header = f"[bold]{i}. {fact_text}[/bold]"
                    if answer_date:
                        header += f"  [dim]({answer_date})[/dim]"
                    lines.append(f"\n{header}")

                    source = f.get("source_quote", "")
                    if source:
                        display_source = fix_bidi(source)
                        if question_id:
                            url = f"https://stips.co.il/ask/{question_id}"
                            lines.append(f'   [@click=app.copy_link("{url}")]🔗[/] [italic dim]"{display_source}"[/italic dim]')
                        else:
                            lines.append(f'   [italic dim]"{display_source}"[/italic dim]')

            facts_widget.update("\n".join(lines) + "\n")

    def action_copy_link(self, url: str) -> None:
        """Copy the Stips question link to the clipboard."""
        self.copy_to_clipboard(url)
        self.notify(f"Link copied to clipboard", title="Clipboard", severity="information")

    def action_export_json(self) -> None:
        """Export the profile tree to a JSON file."""
        export_path = Path(f".cache/{self._user_id}_profile_export.json")
        export_path.parent.mkdir(parents=True, exist_ok=True)

        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(self._profile_data, f, ensure_ascii=False, indent=2)

        self.notify(
            f"Exported to {export_path}",
            title="Export Complete",
            severity="information",
        )

    def action_clear_cache(self) -> None:
        """Clear the current user's cache."""
        if self._cache_clear_callback:
            self._cache_clear_callback()  # type: ignore[operator]
            self.notify(
                f"Cache cleared for user {self._user_id}",
                title="Cache Cleared",
                severity="warning",
            )
        else:
            self.notify(
                "Cache clearing not available",
                severity="error",
            )

    def action_quit(self) -> None:
        """Quit the dashboard."""
        self.exit()