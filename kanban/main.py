"""Entry point for the kanban CLI."""

import logging
from pathlib import Path

from cli.parser import parse_args
from cli.renderer import Renderer

from models import UserContext
from services.git import GitService
from services.kanban import KanbanService
from services.index import IndexService
from storage.filesystem import FilesystemRepository
from storage.memory import InMemoryRepository


def main() -> None:
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    
    cwd = Path.cwd()
    repository = get_repository("filesystem")
    index_service = IndexService(repository=repository)
    git_service = GitService()

    # TODO: acquire user context from environment or config, which may require repository access to determine
    # TODO: map a repository domain Config object to the UserContext model
    user_context = UserContext()
    svc = KanbanService(repository=repository, index_service=index_service, git_service=git_service, user_context=user_context)
    renderer = Renderer()
    
    args = parse_args()

    if not hasattr(args, "func"):
        raise SystemExit("No command handler registered")

    try:
        args.func(args, svc, renderer)
    except ValueError as e:
        print(f"Value error: {e}")

def get_repository(typ: str) -> KanbanRepository:
    import tempfile
    from uuid import uuid4
    temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
    temp_dir.mkdir()
    cwd = Path.cwd()

    if typ == "memory":
        return InMemoryRepository(root=temp_dir)
    elif typ == "filesystem":
        return FilesystemRepository(root=temp_dir)
    
if __name__ == "__main__":
    main()
