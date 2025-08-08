#!/usr/bin/env python

from grader_helper.dependencies import pl  # pathlib as pl


def path_catcher(s: str) -> pl.Path:
    """
    Parse a user‑pasted path string into a Path.
    - Trims whitespace
    - Removes surrounding single/double quotes if present
    - Does NOT touch the filesystem
    """
    if s is None:
        raise ValueError("Path string is empty.")
    try:
        s = s.strip()
        # Strip surrounding quotes like "C:\Users\..." or 'C:\Users\...'
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            s = s[1:-1]
        return pl.Path(s)
    except Exception as e:
        raise ValueError(f"Could not parse the path string: {s!r}") from e


def main():
    inp = input("enter your string here \n:")
    p = path_catcher(inp)
    print(p.as_posix())


if __name__ == "__main__":
    main()
