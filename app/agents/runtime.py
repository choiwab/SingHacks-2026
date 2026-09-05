"""Durable local graph wiring. Use one process per memory directory in the demo."""

from contextlib import contextmanager
from functools import partial
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from app.agents.graph import build_agent_flow
from app.agents.verification import verify_meeting_pack
from app.agents.versioning import generation_policy_version
from app.mcp.client import MCPClient
from app.mcp.service import load_memory
from app.mcp.store import MemoryStore
from app.pipeline.agent_inputs import load_curated_bundle


@contextmanager
def persistent_data_flow(source_dir: Path, memory_dir: Path, *, mcp_url: str | None = None):
    memory_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    checkpoint_path = memory_dir / "checkpoints.sqlite3"
    checkpoint_path.touch(mode=0o600, exist_ok=True)
    store = MemoryStore(memory_dir / "records.sqlite3")
    client = MCPClient(mcp_url) if mcp_url else None
    with SqliteSaver.from_conn_string(str(checkpoint_path)) as saver:
        yield build_agent_flow(
            load_bundle=client.bundle if client else partial(load_curated_bundle, source_dir),
            load_communications=client.context
            if client
            else partial(load_memory, source_dir, store),
            verify_pack=verify_meeting_pack,
            checkpointer=saver,
            record_review=store.record_review,
            generation_policy=generation_policy_version(),
        )
