
def prompt_for_confirmation(message: str, default: bool = False) -> bool:
    """Prompt the user for confirmation with a yes/no question."""
    while True:
        yn = "Y/n" if default else "y/N"
        response = input(f"{message} ({yn}): ").strip().lower()
        if not response:
            return default
        if response in ("y", "yes"):
            return True
        if response in ("n", "no"):
            return False
        else:
            print("Please enter 'y' or 'n'.")