"""Full pipeline: architect + planner + incremental code generation."""
import asyncio
import sys
import time
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent / "output" / "crud_full"

async def main():
    sys.stdout.write("=" * 60 + "\nAI Development Team - Real Pipeline\n" + "=" * 60 + "\n")
    sys.stdout.flush()

    from core.agents.architect import ArchitectAgent
    from core.agents.planner import PlannerAgent
    from core.agents.coder import CoderAgent
    from core.agents.context_builder import ContextBuilder
    from core.agents.syntax_validator import SyntaxValidator
    from core.agents.repair_agent import RepairAgent
    from core.agents.artifact_manager import ArtifactManager
    from core.orchestrator.state import create_initial_state, FileStatus

    state = create_initial_state(
        "pipe-crud-1",
        "Create a simple task CRUD with FastAPI, SQLite, HTML UI"
    )
    state["workspace_path"] = str(OUTPUT)
    total_start = time.time()

    # 1. Architect
    sys.stdout.write("\n[1/4] Architect...\n"); sys.stdout.flush()
    t0 = time.time()
    architect = ArchitectAgent()
    state = await architect.run(state)
    bp = state["project_blueprint"]
    sys.stdout.write(f"  {bp.project_name} ({bp.backend}/{bp.database}) [{time.time()-t0:.1f}s, {state.get('tokens_used')}t]\n")
    sys.stdout.write(f"  {bp.to_human_readable()[:400]}\n")
    sys.stdout.flush()

    # 2. Planner
    sys.stdout.write("\n[2/4] Planner...\n"); sys.stdout.flush()
    t0 = time.time()
    planner = PlannerAgent()
    state = await planner.run(state)
    plan = state["project_plan"]
    sys.stdout.write(f"  {len(plan.files)} files [{time.time()-t0:.1f}s, {state.get('tokens_used')}t]\n")
    for f in plan.files:
        sys.stdout.write(f"    {f.file_path}\n")
    sys.stdout.flush()

    # 3. Generate files
    sys.stdout.write("\n[3/4] Generating files...\n"); sys.stdout.flush()
    t0 = time.time()
    artifact_mgr = ArtifactManager(str(OUTPUT))
    artifact_mgr.save_plan(plan)
    validator = SyntaxValidator()
    repair_agent = RepairAgent()
    coder = CoderAgent()
    ctx_builder = ContextBuilder(plan, bp)

    generated = 0; failed = 0; repaired = 0
    for _ in range(100):
        ready = plan.get_ready_tasks()
        if not ready:
            break
        ft = ready[0]
        ft.status = FileStatus.GENERATING
        sys.stdout.write(f"  {ft.file_path}... "); sys.stdout.flush()

        content = await coder.generate_file(ft, ctx_builder, state)
        if not content:
            ft.status = FileStatus.FAILED; failed += 1
            sys.stdout.write("FAIL (no content)\n"); sys.stdout.flush()
            continue

        # Validate
        ft.status = FileStatus.VALIDATING
        vr = validator.validate(ft.file_path, content)
        if vr.is_valid:
            ft.status = FileStatus.DONE; ft.content = content
            artifact_mgr.save_file(ft.file_path, content)
            artifact_mgr.save_file_status(ft)
            generated += 1
            sys.stdout.write(f"OK ({len(content)}b)\n"); sys.stdout.flush()
        else:
            ft.status = FileStatus.REPAIRING; ft.repair_attempts += 1
            sys.stdout.write(f"SYNTAX: {vr.error_message} -> "); sys.stdout.flush()
            if ft.repair_attempts <= 3:
                fixed = await repair_agent.repair(ft.file_path, content, vr, state)
                if fixed:
                    vr2 = validator.validate(ft.file_path, fixed)
                    if vr2.is_valid:
                        content = fixed; ft.status = FileStatus.DONE; ft.content = content
                        artifact_mgr.save_file(ft.file_path, content)
                        artifact_mgr.save_file_status(ft)
                        repaired += 1; generated += 1
                        sys.stdout.write("REPAIRED\n"); sys.stdout.flush()
                        continue
            ft.status = FileStatus.FAILED; failed += 1
            sys.stdout.write("FAILED\n"); sys.stdout.flush()

    # 4. Report
    total = time.time() - total_start
    sys.stdout.write(f"\n[4/4] Done in {total:.1f}s, {state.get('tokens_used')} tokens\n")
    sys.stdout.write(f"  Generated: {generated}, Failed: {failed}, Repaired: {repaired}\n")
    sys.stdout.write(f"  Output: {OUTPUT}\n")

    if OUTPUT.exists():
        for p in sorted(OUTPUT.rglob("*")):
            if p.is_file() and ".ai_artifacts" not in str(p):
                sys.stdout.write(f"    {p.relative_to(OUTPUT)} ({p.stat().st_size}b)\n")
    sys.stdout.flush()

if __name__ == "__main__":
    asyncio.run(main())