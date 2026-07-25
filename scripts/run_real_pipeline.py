"""Real pipeline execution: CRUD with UI via OpenRouter.

This script runs the full AI Development Team pipeline and generates
a real project into a workspace directory.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.agents.architect import ArchitectAgent
from core.agents.coder import CoderAgent
from core.agents.context_builder import ContextBuilder
from core.agents.planner import PlannerAgent
from core.agents.syntax_validator import SyntaxValidator
from core.agents.repair_agent import RepairAgent
from core.agents.artifact_manager import ArtifactManager
from core.orchestrator.state import (
    AgentState,
    FileStatus,
    ProjectPlan,
    ProjectBlueprint,
    create_initial_state,
)
from core.router.model_router import ModelRouter


REQUEST_TEXT = """
Create a simple task management CRUD application with:

- FastAPI backend with SQLite database
- SQLAlchemy ORM with a Task model (id, title, description, completed, created_at)
- Pydantic schemas for request/response
- Service layer with business logic
- Full CRUD REST API (POST, GET, PUT, DELETE)
- A simple HTML+CSS UI with:
  - List all tasks
  - Create new task form
  - Toggle task completion
  - Delete task
  - Clean, responsive design
- Jinja2 templates for rendering
- Tests for the API endpoints
- Proper error handling
- Type hints throughout
"""

OUTPUT_DIR = Path(__file__).resolve().parent / "output" / "crud_output"


async def main():
    start = time.time()
    print("=" * 60)
    print("AI Development Team - Real Pipeline Execution")
    print("=" * 60)
    print(f"Request: {REQUEST_TEXT.strip()[:80]}...")
    print(f"Output: {OUTPUT_DIR}")
    print()

    # Initialize state without router (uses fallback provider from env vars)
    state = create_initial_state(
        run_id=f"real-crud-{int(time.time())}",
        user_request=REQUEST_TEXT,
        router=None,
    )
    state["workspace_path"] = str(OUTPUT_DIR)

    # Step 1: Architect
    print("[1/5] Architect — designing architecture...")
    t0 = time.time()
    architect = ArchitectAgent()
    state = await architect.run(state)
    bp: ProjectBlueprint = state.get("project_blueprint")
    if not bp:
        print("FAILED: Architect did not produce a blueprint")
        print(f"Error: {state.get('error')}")
        return
    print(f"  ✓ Blueprint: {bp.project_name} ({bp.backend} / {bp.database})")
    print(f"  ✓ Patterns: {', '.join(bp.patterns)}")
    print(f"  ✓ Structure: {len(bp.directory_structure)} dirs")
    print(f"  ⏱  {time.time() - t0:.1f}s")
    print(f"  📋 Summary:\n{bp.to_human_readable()[:500]}")
    print()

    # Step 2: Planner
    print("[2/5] Planner — decomposing into files...")
    t0 = time.time()
    planner = PlannerAgent()
    state = await planner.run(state)
    project_plan: ProjectPlan = state.get("project_plan")
    if not project_plan:
        print("FAILED: Planner did not produce a plan")
        print(f"Error: {state.get('error')}")
        return
    print(f"  ✓ {len(project_plan.files)} files to generate")
    for f in project_plan.files:
        deps = f" (depends: {', '.join(f.dependencies)})" if f.dependencies else ""
        print(f"    - {f.file_path}{deps}")
    print(f"  ⏱  {time.time() - t0:.1f}s")
    print()

    # Step 3: Generate files one by one
    print("[3/5] Coder — generating files incrementally...")
    t0 = time.time()

    artifact_mgr = ArtifactManager(str(OUTPUT_DIR))
    artifact_mgr.save_plan(project_plan)

    validator = SyntaxValidator()
    repair_agent = RepairAgent()
    coder = CoderAgent()
    context_builder = ContextBuilder(project_plan, bp)

    total_files = len(project_plan.files)
    generated = 0
    failed = 0
    repaired = 0

    iteration = 0
    max_iterations = 50  # safety limit

    while iteration < max_iterations:
        iteration += 1
        ready_tasks = project_plan.get_ready_tasks()

        if not ready_tasks:
            if project_plan.all_done():
                print(f"  ✓ All {total_files} files generated successfully")
                break
            elif project_plan.has_failures():
                print(f"  ✗ Some files failed — cannot continue")
                break
            else:
                # Dependencies not yet met — should not happen in practice
                pending = [t for t in project_plan.files if t.status == FileStatus.PENDING]
                print(f"  ? Waiting for dependencies: {[t.file_path for t in pending]}")
                break

        file_task = ready_tasks[0]
        print(f"    Generating: {file_task.file_path}...", end="")

        file_task.status = FileStatus.GENERATING

        # Generate
        content = await coder.generate_file(file_task, context_builder, state)
        if content is None:
            file_task.status = FileStatus.FAILED
            file_task.error = "Generation request returned None"
            print(" ✗ LLM returned None")
            failed += 1
            artifact_mgr.save_generation_log(file_task.file_path, "generate", False, "None content")
            continue

        # Validate
        file_task.status = FileStatus.VALIDATING
        validation = validator.validate(file_task.file_path, content)

        if validation.is_valid:
            file_task.status = FileStatus.DONE
            file_task.content = content
            artifact_mgr.save_file(file_task.file_path, content)
            artifact_mgr.save_file_status(file_task)
            artifact_mgr.save_generation_log(file_task.file_path, "generate", True)
            generated += 1
            print(f" ✓ ({len(content)} bytes)")
        else:
            # Attempt repair
            file_task.status = FileStatus.REPAIRING
            file_task.repair_attempts += 1

            print(f" ⚠ syntax error ({validation.error_message})", end="")

            if file_task.repair_attempts <= 3:
                repaired_content = await repair_agent.repair(
                    file_task.file_path, content, validation, state
                )
                if repaired_content:
                    re_validation = validator.validate(file_task.file_path, repaired_content)
                    if re_validation.is_valid:
                        content = repaired_content
                        file_task.status = FileStatus.DONE
                        file_task.content = content
                        artifact_mgr.save_file(file_task.file_path, content)
                        artifact_mgr.save_file_status(file_task)
                        artifact_mgr.save_generation_log(
                            file_task.file_path, "repair", True
                        )
                        generated += 1
                        repaired += 1
                        print(f" → repaired ✓ ({len(content)} bytes)")
                        continue

            file_task.status = FileStatus.FAILED
            file_task.error = validation.error_message
            artifact_mgr.save_generation_log(
                file_task.file_path, "validate", False, validation.error_message
            )
            failed += 1
            print(f" → failed")

    print(f"  ⏱  {time.time() - t0:.1f}s")
    print(f"  📊 Generated: {generated}, Failed: {failed}, Repaired: {repaired}")
    print()

    # Step 4: Tester (skipped — no actual test environment)
    print("[4/5] Tester — skipping (no test environment in this run)")
    state["test_results"] = None
    state["status"] = "testing"
    print()

    # Step 5: Report
    total_time = time.time() - start
    total_tokens = state.get("tokens_used", 0)

    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"  Project: {bp.project_name}")
    print(f"  Files generated: {generated}/{total_files}")
    print(f"  Files failed: {failed}")
    print(f"  Files repaired: {repaired}")
    print(f"  Tokens used: {total_tokens}")
    print(f"  Total time: {total_time:.1f}s")
    print(f"  Output directory: {OUTPUT_DIR}")
    print()

    # List generated files
    if OUTPUT_DIR.exists():
        print("Generated files:")
        for p in sorted(OUTPUT_DIR.rglob("*")):
            if p.is_file() and ".ai_artifacts" not in str(p):
                print(f"  {p.relative_to(OUTPUT_DIR)} ({p.stat().st_size} bytes)")


if __name__ == "__main__":
    asyncio.run(main())
