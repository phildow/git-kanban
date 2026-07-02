"""Entry point for the kanban CLI."""

import logging
from pathlib import Path

from .cli.parser import parse_args
from .cli.renderer import Renderer
from .cli.json_renderer import JsonRenderer

from .services.git import GitService
from .services.kanban import KanbanService
from .index.memory import InMemoryIndexService
from .storage.filesystem import FilesystemRepository
from .storage.base import KanbanRepository, RepositoryAlreadyInitialized
from .storage.memory import InMemoryRepository
from .utils.debug import __DEBUG__, FILESYSTEM, MEMORY

def main() -> None:
    """Main entry point for the kanban CLI."""
    setup_logging(logging.DEBUG)
    
    repository = get_repository(FILESYSTEM)
    index_service = InMemoryIndexService(repository=repository)
    git_service = GitService()
    svc = KanbanService(repository=repository, index_service=index_service, git_service=git_service)
    renderer = Renderer()
    json_renderer = JsonRenderer()

    args = parse_args()

    if not hasattr(args, "func"):
        raise SystemExit("No command handler registered")

    try:
        args.func(args, svc, renderer, json_renderer)
    except RepositoryAlreadyInitialized as e:
        logging.error("Error: %s", str(e))
        print(f"Error: Repository already initialized")
    except Exception as e:
        exc_desc = str(e) or e.__class__.__name__
        logging.error("Error: %s", exc_desc)
        print(f"Error: {e}")

def setup_logging(level: int) -> None:
    """Configure logging to write to a file in the user's home directory."""
    logfile = Path("~/.kanban/kanban.log").expanduser()

    if not logfile.parent.exists():
        logfile.parent.mkdir(parents=True, exist_ok=True)
        
    logging.basicConfig(filename=str(logfile),
                        filemode="a",
                        level=level,
                        format='%(asctime)s - %(levelname)s - %(message)s')

def get_repository(typ: str) -> KanbanRepository:
    """Returns the appropriate KanbanRepository implementation based on the specified type."""
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
