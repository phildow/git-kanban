"""Entry point for the kanban CLI."""

from cli.noun_first_parser import parse_args
from cli.renderer import Renderer

from models import UserContext
from services.git_service import GitService
from services.kanban_service import KanbanService
from services.index_service import IndexService
from storage.memory_repository import InMemoryRepository

def main() -> None:
    repository = InMemoryRepository()
    index_service = IndexService(repository=repository)
    git_service = GitService()

    # TODO: acquire user context from environment or config, which may require repository access to determine
    # TODO: map a repository domain Config object to the UserContext model
    user_context = UserContext()
    svc = KanbanService(repository=repository, index_service=index_service, git_service=git_service, user_context=user_context)
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
