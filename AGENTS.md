# AGENTS.md

## Documentation

- See ``README.md`` for usage documentation.
- When adding new functionality or modifying existing functionality, ``README.md`` should be updated.

## Dependencies

- Dependencies are defined in ``requirements.txt``.
- When a new dependency is added, ``requirements.txt`` should be updated.

## Code Standards

- When adding new code or modifying existing code:
  - Duplicate code should be avoided by refactoring the code.
  - Functions should be kept relatively small (200 lines of code or less).
- Useful debug messages should be printed when applicable:
  - If a function or its calling functions print debug output, the function should accept a ``kwarg`` named ``debug`` that is a ``Boolean``.
- Useful warning messages should be printed when applicable:
- Useful error messages should be printed when applicable:
  - If a fatal exception is encountered, a backtrace should be printed.
  - If debug mode is enabled and no exception is encountered, a backtrace of the current call stack should be printed.

## Tests

- Tests are located in the ``tests/`` directory
- When adding new code or fixing bugs, new tests should be added.
- Tests should not actually run commands that can have side effects
  - Use mock instead.
  - If example output is needed to simulate expected behavior, request it.

