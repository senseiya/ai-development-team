"""Test 3 simple projects with UI using the AI Development Team pipeline.

Each project is a small FastAPI + SQLite + HTML/CSS app:
  1. Task Manager — CRUD de tareas
  2. Calculator — Calculadora web
  3. Notes App — Aplicación de notas

Usage:
    python scripts/test_3_projects.py
"""

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.agents.architect import ArchitectAgent
from core.agents.coder import CoderAgent
from core.agents.context_builder import ContextBuilder
from core.agents.planner import PlannerAgent
from core.agents.syntax_validator import SyntaxValidator
from core.agents.repair_agent import RepairAgent
from core.agents.artifact_manager import ArtifactManager
from core.orchestrator.state import (
    FileStatus,
    ProjectPlan,
    ProjectBlueprint,
    create_initial_state,
)


PROJECTS = [
    {
        "name": "task_manager",
        "request": (
            "Create a simple task manager with:\n"
            "- FastAPI backend with SQLite (via SQLAlchemy)\n"
            "- Task model: id (int), title (str), description (str), done (bool)\n"
            "- Full CRUD REST API\n"
            "- A clean HTML+CSS UI with:\n"
            "  - List of tasks with checkboxes to toggle done\n"
            "  - Form to create new tasks\n"
            "  - Delete button per task\n"
            "- Jinja2 templates"
        ),
    },
    {
        "name": "calculator",
        "request": (
            "Create a web calculator with:\n"
            "- FastAPI backend (no database needed)\n"
            "- POST /calculate endpoint that accepts: operation (add/subtract/multiply/divide), a (float), b (float)\n"
            "- Returns result as JSON\n"
            "- A clean HTML+CSS UI with:\n"
            "  - Display showing current input\n"
            "  - Number buttons (0-9)\n"
            "  - Operation buttons (+, -, *, /)\n"
            "  - Equals button that calls the API\n"
            "  - Clear button\n"
            "- Jinja2 template for the calculator page"
        ),
    },
    {
        "name": "notes_app",
        "request": (
            "Create a simple notes app with:\n"
            "- FastAPI backend with SQLite (via SQLAlchemy)\n"
            "- Note model: id (int), title (str), content (str), created_at (datetime)\n"
            "- Full CRUD REST API\n"
            "- A clean HTML+CSS UI with:\n"
            "  - Grid/list of note cards showing title and preview\n"
            "  - Form to create/edit notes\n"
            "  - Delete button per note\n"
            "  - Markdown-style rendering for note content\n"
            "- Jinja2 templates"
        ),
    },
]

OUTPUT_BASE = Path(__file__).resolve().parent / "output" / "test_projects"


AGENT_DELAY = 8  # seconds between agents to avoid 429


async def run_with_backoff(coro_factory, label: str, max_retries: int = 3):
    """Run a coroutine with retry + exponential backoff on 429 errors."""
    for attempt in range(1, max_retries + 1):
        try:
            return await coro_factory()
        except Exception as e:
            if "429" in str(e) and attempt < max_retries:
                wait = 5 * (2 ** (attempt - 1))
                print(f"    429 rate limit on {label}, waiting {wait}s (attempt {attempt}/{max_retries})...")
                await asyncio.sleep(wait)
            else:
                raise


async def run_one_project(project: dict, index: int) -> dict:
    """Run the full pipeline for a single project. Returns a result dict."""
    name = project["name"]
    request = project["request"]
    output_dir = OUTPUT_BASE / name
    output_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "name": name,
        "status": "failed",
        "files_generated": 0,
        "files_failed": 0,
        "files_repaired": 0,
        "total_files": 0,
        "tokens": 0,
        "time_s": 0.0,
        "error": None,
    }

    start = time.time()

    try:
        # Create initial state
        state = create_initial_state(
            run_id=f"test3-{name}-{int(time.time())}",
            user_request=request,
        )
        state["workspace_path"] = str(output_dir)

        # 1. Architect (with retry)
        print(f"  [{name}] Architect...")
        t0 = time.time()
        architect = ArchitectAgent()
        state = await run_with_backoff(lambda: architect.run(state), "architect")
        bp: ProjectBlueprint | None = state.get("project_blueprint")
        if not bp:
            result["error"] = "Architect produced no blueprint"
            print(f"  [{name}] FAILED: no blueprint")
            return result
        print(f"  [{name}] Blueprint: {bp.project_name} ({bp.backend}/{bp.database}) [{time.time()-t0:.1f}s]")

        # Delay before next agent
        print(f"  [{name}] Waiting {AGENT_DELAY}s before Planner...")
        await asyncio.sleep(AGENT_DELAY)

        # 2. Planner (with retry)
        print(f"  [{name}] Planner...")
        t0 = time.time()
        planner = PlannerAgent()
        state = await run_with_backoff(lambda: planner.run(state), "planner")
        plan: ProjectPlan | None = state.get("project_plan")
        if not plan:
            result["error"] = "Planner produced no plan"
            print(f"  [{name}] FAILED: no plan")
            return result
        result["total_files"] = len(plan.files)
        print(f"  [{name}] {len(plan.files)} files [{time.time()-t0:.1f}s]")

        # 3. Generate files
        print(f"  [{name}] Generating files...")
        t0 = time.time()
        artifact_mgr = ArtifactManager(str(output_dir))
        artifact_mgr.save_plan(plan)
        validator = SyntaxValidator()
        repair_agent = RepairAgent()
        coder = CoderAgent()
        ctx_builder = ContextBuilder(plan, bp)

        max_iter = 100
        for _ in range(max_iter):
            ready = plan.get_ready_tasks()
            if not ready:
                break
            ft = ready[0]
            ft.status = FileStatus.GENERATING

            content = await coder.generate_file(ft, ctx_builder, state)
            if not content:
                ft.status = FileStatus.FAILED
                result["files_failed"] += 1
                continue

            ft.status = FileStatus.VALIDATING
            vr = validator.validate(ft.file_path, content)
            if vr.is_valid:
                ft.status = FileStatus.DONE
                ft.content = content
                artifact_mgr.save_file(ft.file_path, content)
                artifact_mgr.save_file_status(ft)
                result["files_generated"] += 1
            else:
                ft.status = FileStatus.REPAIRING
                ft.repair_attempts += 1
                if ft.repair_attempts <= 3:
                    fixed = await repair_agent.repair(ft.file_path, content, vr, state)
                    if fixed:
                        vr2 = validator.validate(ft.file_path, fixed)
                        if vr2.is_valid:
                            content = fixed
                            ft.status = FileStatus.DONE
                            ft.content = content
                            artifact_mgr.save_file(ft.file_path, content)
                            artifact_mgr.save_file_status(ft)
                            result["files_repaired"] += 1
                            result["files_generated"] += 1
                            continue
                ft.status = FileStatus.FAILED
                result["files_failed"] += 1

        print(f"  [{name}] Generated: {result['files_generated']}, Failed: {result['files_failed']}, Repaired: {result['files_repaired']} [{time.time()-t0:.1f}s]")

        result["tokens"] = state.get("tokens_used", 0)
        result["status"] = "success" if result["files_generated"] > 0 else "failed"

    except Exception as e:
        result["error"] = str(e)
        print(f"  [{name}] EXCEPTION: {e}")

    result["time_s"] = time.time() - start
    return result


async def main():
    print("=" * 60)
    print("  AI Development Team — 3 Project Test")
    print("=" * 60)
    print()

    results = []
    for i, project in enumerate(PROJECTS[:1], 1):  # Solo el primero
        print(f"[{i}/3] {project['name'].upper()}")
        print("-" * 40)
        r = await run_one_project(project, i)
        results.append(r)
        print()

    # Summary
    print("=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    total_time = 0
    total_files = 0
    total_tokens = 0
    for r in results:
        status_icon = "OK" if r["status"] == "success" else "FAIL"
        print(f"  [{status_icon}] {r['name']}: {r['files_generated']}/{r['total_files']} files, {r['time_s']:.1f}s, {r['tokens']}t")
        if r["error"]:
            print(f"       Error: {r['error']}")
        total_time += r["time_s"]
        total_files += r["files_generated"]
        total_tokens += r["tokens"]
    print(f"\n  Total: {total_files} files, {total_time:.1f}s, {total_tokens} tokens")

    # List output dirs
    print(f"\n  Output: {OUTPUT_BASE}")
    for p in sorted(OUTPUT_BASE.rglob("*")):
        if p.is_file() and ".ai_artifacts" not in str(p):
            print(f"    {p.relative_to(OUTPUT_BASE)} ({p.stat().st_size}b)")


if __name__ == "__main__":
    asyncio.run(main())
