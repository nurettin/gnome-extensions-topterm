"""Remember each tab's directory and foreground command across topterm restarts.

A tab that was running Claude Code is resumed with `claude --resume <session>`; any other
command is typed back at the prompt without running it.
"""
import json
import os
import shlex
from dataclasses import asdict, dataclass
from pathlib import Path

# Claude Code keeps one file per running process, named by pid, holding the live `sessionId`.
CLAUDE_SESSIONS_DIR = Path.home() / ".claude" / "sessions"
# Session-picking flags, replaced by `--resume <session>` on restore.
CLAUDE_SESSION_FLAGS = ("-c", "--continue", "--fork-session")
CLAUDE_SESSION_VALUE_FLAGS = ("-r", "--resume", "--session-id")


@dataclass
class TabState:
    title: str
    cwd: str
    command: list[str] | None  # argv of the foreground job; None at an idle prompt
    claude_session: str | None  # set when the foreground job is Claude Code

    def typed(self) -> str | None:
        """Text to type at the restored tab's first prompt; the newline runs a Claude resume."""
        if self.claude_session is not None:
            return shlex.join(claude_resume_argv(self.command, self.claude_session)) + "\n"
        if self.command is not None:
            return shlex.join(self.command)
        return None


def default_path() -> Path:
    return Path.home() / ".local" / "state" / "topterm" / "tabs.json"


def load(path: Path) -> list[TabState]:
    if not path.exists():
        return []
    return [TabState(**tab) for tab in json.loads(path.read_text())]


def save(path: Path, tabs: list[TabState]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps([asdict(tab) for tab in tabs], indent=2))
    tmp.replace(path)  # atomic, so a reboot mid-write never leaves half a file


def snapshot(title: str, shell_pid: int) -> TabState | None:
    """The tab's state, or None when its shell has already exited and the tab is closing."""
    try:
        cwd = os.readlink(f"/proc/{shell_pid}/cwd")
        stat = Path(f"/proc/{shell_pid}/stat").read_text()
    except FileNotFoundError:
        return None
    # Fields after the parenthesised comm: state ppid pgrp session tty_nr tpgid ...
    job = int(stat.rsplit(")", 1)[1].split()[5])
    try:
        command = [arg.decode() for arg in Path(f"/proc/{job}/cmdline").read_bytes().split(b"\0")[:-1]]
    except FileNotFoundError:  # the job exited since tpgid was read
        command = []
    if job == shell_pid or not command:
        return TabState(title=title, cwd=cwd, command=None, claude_session=None)
    try:
        session = json.loads((CLAUDE_SESSIONS_DIR / f"{job}.json").read_text())["sessionId"]
    except FileNotFoundError:  # not Claude Code, or Claude has not written its session file yet
        session = None
    return TabState(title=title, cwd=cwd, command=command, claude_session=session)


def claude_resume_argv(command: list[str], session: str) -> list[str]:
    """The original Claude Code argv with its session-picking flags replaced by `--resume <session>`."""
    argv: list[str] = []
    args = iter(command)
    for arg in args:
        name = arg.split("=", 1)[0]
        if arg in CLAUDE_SESSION_FLAGS or (name in CLAUDE_SESSION_VALUE_FLAGS and name != arg):
            continue
        if arg in CLAUDE_SESSION_VALUE_FLAGS:
            value = next(args, None)
            if value is not None and value.startswith("-"):  # bare --resume: the next token is a flag
                argv.append(value)
            continue
        argv.append(arg)
    return [*argv, "--resume", session]
