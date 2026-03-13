import subprocess
from dataclasses import dataclass
from typing import List, Mapping, Optional


@dataclass
class CommandResult:
    stdout: str
    stderr: str


class CommandError(RuntimeError):
    def __init__(self, message: str, result: Optional[CommandResult] = None):
        super().__init__(message)
        self.result = result


def run_command(args: List[str], timeout_s: int, env: Optional[Mapping[str, str]] = None) -> CommandResult:
    try:
        result = subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env=dict(env) if env is not None else None,
        )
        return CommandResult(stdout=result.stdout or "", stderr=result.stderr or "")
    except subprocess.TimeoutExpired as exc:
        raise CommandError(f"command timed out after {timeout_s}s: {' '.join(args)}") from exc
    except subprocess.CalledProcessError as exc:
        cmd_result = CommandResult(stdout=exc.stdout or "", stderr=exc.stderr or "")
        raise CommandError(f"command failed: {' '.join(args)}", result=cmd_result) from exc
