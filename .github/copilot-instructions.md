# Copilot Instructions

## Python

- Use python as the programming language
- The name of the root python package is `kanban`
- Use dot notation instead `getattr`, especially when the type is known
- Prefer explicit types over `object` and add type whenever possible
- Use double quotes `"..."` for strings
- When typing optionals prefer `typ | None` instead of `Optional(typ)`
- When a python dependency is required add it to pyproject.toml
- Add documentation when creating types and methods, including for tests
- Break up tests, keep unit tests small
- Run tests from the current working directory with the bash command `python -m unittest discover -s tests`
- Tab indent key-value pairs in INI files
