"""Documented process exit codes for monarch-cli."""

EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_INPUT_NEEDED = EXIT_USAGE

EXIT_CODES: dict[str, str] = {
    str(EXIT_SUCCESS): "success",
    str(EXIT_ERROR): "general error",
    str(EXIT_USAGE): "usage error",
}
