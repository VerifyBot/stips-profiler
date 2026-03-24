"""
Stips Profiler — Main Orchestrator (CLI Entry Point).

Wires together all modules:
  Scraper → Cache → AI Engine → TUI Dashboard

Supports both interactive mode and direct CLI invocation.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Load .env before anything else
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from openai import OpenAI

from src.cache.storage import CacheStorage
from src.scraper.client import StipsClient, StipsClientError
from src.ai.engines import (
    EmbeddingsEngine,
    PromptCachingEngine,
    UserProfileTree,
)
from src.ui.cli_flow import (
    ProgressDisplay,
    console,
    screen_ai_cache_prompt,
    screen_boot,
    screen_cache_update_prompt,
    screen_engine_selection,
    screen_precheck,
    screen_progress_cached,
)
from src.ui.dashboard import ProfileDashboard

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("stips_profiler")


# ---------------------------------------------------------------------------
# Core orchestration
# ---------------------------------------------------------------------------
async def run(user_id_arg: str | None = None, force_refresh: bool = False) -> None:
    """Main application flow."""
    cache = CacheStorage()
    stips = StipsClient()
    openai_client = OpenAI()  # Uses OPENAI_API_KEY from env

    try:
        # ==============================================================
        # Screen 1: Get User ID
        # ==============================================================
        if user_id_arg:
            user_id_str = user_id_arg
        else:
            user_id_str = screen_boot()

        try:
            user_id = int(user_id_str)
        except ValueError:
            console.print(f"[bold red]✗ Invalid User ID: '{user_id_str}'[/bold red]")
            return

        # ==============================================================
        # Screen 2: Fast Pre-Check (one lightweight API call)
        # ==============================================================
        console.print()
        console.print("[dim]Fetching user metadata...[/dim]")

        try:
            user_meta = await stips.fetch_user_meta(user_id)
        except StipsClientError as exc:
            console.print(f"[bold red]✗ Failed to fetch user: {exc}[/bold red]")
            return

        nickname = user_meta["nickname"]
        flower_count = user_meta["flower_count"]
        age = user_meta.get("age")

        # Save/update user meta in cache
        cache.save_user_meta(
            user_id=user_id,
            nickname=nickname,
            flower_count=flower_count,
            raw_profile=user_meta.get("_raw", {}),
        )

        cached_count = cache.get_response_count(user_id)

        screen_precheck(
            user_id=user_id,
            nickname=nickname,
            flower_count=flower_count,
            cached_count=cached_count,
            age=age,
        )

        # ==============================================================
        # Screen 2b: Check cache freshness
        # ==============================================================
        need_fetch = True
        cached_meta = cache.get_user_meta(user_id)

        if force_refresh:
            console.print("[yellow]--force-refresh: clearing cache...[/yellow]")
            cache.clear_user_cache(user_id)
            # Re-save the fresh metadata
            cache.save_user_meta(
                user_id=user_id,
                nickname=nickname,
                flower_count=flower_count,
                raw_profile=user_meta.get("_raw", {}),
            )
            cached_count = 0
        elif cached_count > 0:
            # We have cached responses — check if the count changed
            old_flower_count = cached_meta.get("flower_count", 0) if cached_meta else 0
            if old_flower_count != flower_count:
                # Flower count changed — ask user
                should_update = screen_cache_update_prompt(
                    cached_flowers=old_flower_count,
                    current_flowers=flower_count,
                )
                if not should_update:
                    need_fetch = False
            else:
                need_fetch = False  # Cache is fresh

        # ==============================================================
        # Screen 3: Engine Selection
        # ==============================================================
        total_count = flower_count if need_fetch else cached_count
        engine_choice = screen_engine_selection(total_count)

        # ==============================================================
        # Screen 3b: Check for cached AI results
        # ==============================================================
        use_cached_ai = False
        cached_ai = cache.get_ai_results(user_id, engine_choice)
        if cached_ai and not force_refresh:
            cached_profile_dict, cached_at = cached_ai
            use_cached_ai = screen_ai_cache_prompt(engine_choice, cached_at)

        # ==============================================================
        # Screen 4: Heavy Lift — Fetch + Process
        # ==============================================================
        console.print()
        progress = ProgressDisplay()
        progress.start()

        # --- Step 4a: Fetch responses ---
        responses: list[dict] = []

        if need_fetch and cached_count < flower_count:
            progress.add_task("fetch", "Fetching responses from Stips API...", total=flower_count)

            known_ids = cache.get_all_answer_ids(user_id) if cached_count > 0 else set()

            async def _on_page(page_num: int, items_so_far: int) -> None:
                progress.update_task("fetch", completed=items_so_far)

            try:
                new_answers = await stips.fetch_flowered_answers(
                    user_id=user_id,
                    known_answer_ids=known_ids,
                    on_page_fetched=_on_page,
                )
                if new_answers:
                    inserted = cache.save_responses(user_id, new_answers)
                    progress.complete_task(
                        "fetch",
                        f"[green]✓[/green] Fetched {inserted:,} new responses from Stips API",
                    )
                else:
                    progress.complete_task(
                        "fetch",
                        "[green]✓[/green] No new responses to fetch",
                    )
            except StipsClientError as exc:
                progress.complete_task(
                    "fetch",
                    f"[red]✗[/red] Fetch failed: {exc}",
                )
                logger.error("Fetch failed: %s", exc)

            responses = cache.get_responses(user_id)
        else:
            # All from cache
            responses = cache.get_responses(user_id)
            screen_progress_cached(len(responses))

        if not responses:
            progress.stop()
            console.print("[bold red]✗ No responses found. Cannot build profile.[/bold red]")
            return

        # --- Step 4b: AI Processing ---
        profile_tree: UserProfileTree | None = None

        if use_cached_ai and cached_ai:
            # Load from cache — skip AI entirely
            progress.stop()
            cached_profile_dict, _ = cached_ai
            profile_tree = UserProfileTree(**cached_profile_dict)
            console.print(
                f"  [bold green]✓[/bold green] Loaded AI profile from [cyan]cache[/cyan]"
            )
        elif engine_choice == "prompt_caching":
            progress.add_task("llm", "LLM extracting facts...", total=4)
            engine = PromptCachingEngine(openai_client)

            def _on_cat_done(trunk_key: str) -> None:
                trunk_labels = {
                    "personal_and_demographic": "Personal & Demographic",
                    "education_and_career": "Education & Career",
                    "social_and_family": "Social & Family",
                    "interests_and_beliefs": "Interests & Beliefs",
                }
                label = trunk_labels.get(trunk_key, trunk_key)
                progress.update_task("llm", advance=1, description=f"LLM: {label} ✓")

            profile_tree = await engine.extract(
                responses=responses,
                on_category_done=_on_cat_done,
            )
            progress.complete_task("llm", "[green]✓[/green] AI extraction complete")

            # Cache the AI results
            cache.save_ai_results(
                user_id, engine_choice, profile_tree.to_serializable_dict()
            )

        else:  # embeddings
            progress.add_task("embed", "Generating vector embeddings...", total=len(responses))
            progress.add_task("llm", "LLM extracting facts (RAG)...", total=4)

            cached_embeddings = cache.get_embeddings(user_id)

            engine = EmbeddingsEngine(openai_client)

            def _on_embed_done() -> None:
                progress.complete_task(
                    "embed",
                    f"[green]✓[/green] Generated embeddings for {len(responses):,} responses",
                )

            def _on_cat_done_rag(trunk_key: str) -> None:
                trunk_labels = {
                    "personal_and_demographic": "Personal & Demographic",
                    "education_and_career": "Education & Career",
                    "social_and_family": "Social & Family",
                    "interests_and_beliefs": "Interests & Beliefs",
                }
                label = trunk_labels.get(trunk_key, trunk_key)
                progress.update_task("llm", advance=1, description=f"LLM (RAG): {label} ✓")

            profile_tree, (new_ids, new_matrix) = await engine.extract(
                responses=responses,
                cached_embeddings=cached_embeddings,
                on_embeddings_done=_on_embed_done,
                on_category_done=_on_cat_done_rag,
            )
            progress.complete_task("llm", "[green]✓[/green] AI extraction complete (RAG)")

            # Cache the embeddings for future runs
            cache.save_embeddings(user_id, new_ids, new_matrix)

            # Cache the AI results
            cache.save_ai_results(
                user_id, engine_choice, profile_tree.to_serializable_dict()
            )

        progress.stop()

        if profile_tree is None:
            console.print("[bold red]✗ AI extraction returned no results.[/bold red]")
            return

        total_facts = profile_tree.total_facts()
        console.print()
        console.print(
            f"[bold green]✓ Profile built! {total_facts} facts extracted.[/bold green]"
        )
        console.print("[dim]Launching interactive dashboard...[/dim]")
        console.print()

        # ==============================================================
        # Screen 5-6: Interactive Dashboard (Textual)
        # ==============================================================
        display_data = profile_tree.to_display_dict()

        app = ProfileDashboard(
            profile_data=display_data,
            user_id=user_id,
            nickname=nickname,
            cache_clear_callback=lambda: cache.clear_user_cache(user_id),
            responses=responses,
        )
        await app.run_async()

    finally:
        await stips.close()
        cache.close()


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stips Profiler — AI-powered psychological profiling from Stips Q&A data",
    )
    parser.add_argument(
        "--user",
        type=str,
        default=None,
        help="Stips User ID (skips the boot screen)",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Clear cache and re-fetch all data",
    )
    args = parser.parse_args()

    try:
        asyncio.run(run(user_id_arg=args.user, force_refresh=args.force_refresh))
    except KeyboardInterrupt:
        console.print("\n[dim]Bye![/dim]")
        sys.exit(0)


if __name__ == "__main__":
    main()
