"""Entry point for the kanban CLI."""

import logging
from pathlib import Path

from cli.parser import parse_args
from cli.renderer import Renderer
from cli.json_renderer import JsonRenderer

from models import UserContext
from services.git import GitService
from services.kanban import KanbanService
from services.index import IndexService
from storage.filesystem import FilesystemRepository
from storage.memory import InMemoryRepository

__DEBUG__ = True

FILESYSTEM = "filesystem"
MEMORY = "memory"

def main() -> None:
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    
    repository = get_repository(FILESYSTEM)
    index_service = IndexService(repository=repository)
    git_service = GitService()
    svc = KanbanService(repository=repository, index_service=index_service, git_service=git_service)
    renderer = Renderer()
    json_renderer = JsonRenderer()

    args = parse_args()

    if not hasattr(args, "func"):
        raise SystemExit("No command handler registered")

    try:
        args.func(args, svc, renderer, json_renderer)
    except ValueError as e:
        print(f"Error: {e}")

def get_repository(typ: str) -> KanbanRepository:
    import tempfile
    from uuid import uuid4

    if __DEBUG__:
        # ID = uuid4().hex[:8]
        ID = "test"
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{ID}"
        if not temp_dir.exists():
            temp_dir.mkdir()
        cwd = temp_dir
    else:  
        cwd = Path.cwd()

    if typ == MEMORY:
        return InMemoryRepository(root=cwd)
    elif typ == FILESYSTEM:
        return FilesystemRepository(root=cwd)
    
if __name__ == "__main__":
    main()
