"""Entry point for the kanban CLI."""

from cli.noun_first_parser import parse_args
from cli.renderer import Renderer
from services.kanban_service import KanbanService
from storage.memory_repository import InMemoryRepository

def main() -> None:
    repository = InMemoryRepository()
    svc = KanbanService(repository=repository)
    renderer = Renderer()

    # Bootstrap the repository during development
    if isinstance(repository, InMemoryRepository):
        svc.init() # calls repository.init
        repository.bootstrap()

    args = parse_args()

    if not hasattr(args, "func"):
        raise SystemExit("No command handler registered")

    try:
        args.func(args, svc, renderer)
    except ValueError as e:
        print(f"Value error: {e}")


if __name__ == "__main__":
    main()
