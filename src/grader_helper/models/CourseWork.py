
#!/usr/bin/env python

from enum import Enum
from typing import Self
from grader_helper.dependencies import (
    BaseModel, ConfigDict, pl, datetime, PositiveFloat,
    PrivateAttr, pd, np, log
)
from grader_helper.helpers import path_cathcer


class CourseWorkType(Enum):
    Exam = "exam"
    Assignment = "assignment"
    Online_MCQ = "online_mcq"
    InPerson_MCQ = "inperson_mcq"


class CourseWork(BaseModel):
    """Represents one piece of coursework.

    Public (persisted) fields store metadata and a path to the class list.
    The in‑memory class list is held in a private attribute and never serialized.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    root: pl.Path
    weight: PositiveFloat
    graders: list[str] = []  # default to list to avoid None/len issues
    class_list_path: pl.Path | None = None  # persisted path only
    _class_list: pd.DataFrame | None = PrivateAttr(
        default=None)  # runtime only
    type: CourseWorkType
    due_date: datetime.datetime
    rubric: pl.Path
    feedback_sheet: pl.Path
    ready: bool = False
    completed: bool = False

    # ---------- Runtime data management ----------

    def set_class_list_path(self, path: pl.Path | str, update: bool = False) -> Self:
        """
        Set the persisted path to the class list file.

        Parameters
        ----------
        path : pathlib.Path | str
            User-provided path to the class list.
        update : bool
            If False and a path already exists, raise to avoid accidental overwrite.

        Returns
        -------
        Self

        Raises
        ------
        ValueError
            If a path is already set and update is False, or the string cannot be parsed.
        TypeError
            If `path` is neither str nor Path.
        FileNotFoundError
            If `path` does not exist on disk.  (Keep/omit per v1 policy.)
        """
        if self.class_list_path is not None and not update:
            raise ValueError(
                "Class list path is already set. Call with update=True to replace it."
            )

        if isinstance(path, str):
            parsed = path_catcher(path)
        elif isinstance(path, pl.Path):
            parsed = path
        else:
            raise TypeError("`path` must be a str or a pathlib.Path.")

        # v1 guardrails (enable if desired)
        if not parsed.exists():
            raise FileNotFoundError(f"No such file or directory: {parsed}")
        if parsed.suffix.lower() not in {".xlsx", ".csv"}:
            raise ValueError(f"Unsupported class list type: {parsed.suffix}")

        self.class_list_path = parsed
        return self

    def load_class_list(self) -> Self:
        """Load the class list DataFrame from `class_list_path`."""
        if self.class_list_path is None:
            raise FileNotFoundError(
                "No class_list_path set. Provide a path or call set_class_list_path() with a pl.Path or str object."
            )
        if not self.class_list_path.exists():
            raise FileNotFoundError(
                f"Class list file not found: {self.class_list_path}"
            )
        if self.class_list_path.suffix.lower() != FileType.XL.value:
            raise ValueError(
                f"Expected an Excel (.xlsx) class list, got {
                    self.class_list_path.suffix!r}."
            )

        try:
            df = pd.read_excel(self.class_list_path)
        except Exception as e:  # pragma: no cover
            raise RuntimeError("Failed to read class list Excel file.") from e

        df.columns = [
            str(c).lower().strip().replace(" ", "_").replace("-", "_")
            for c in df.columns
        ]
        # create a coursework-specific column (blank) if absent
        cw_col = self.name.lower().replace(" ", "_").strip()
        if cw_col not in df.columns:
            df.insert(len(df.columns), cw_col, "")

        self._class_list = df
        return self

    # ---------- Admin operations ----------

    def set_graders(self, file: pl.Path) -> Self:
        """Load graders from a text file (one name per line)."""
        if self.graders:  # already set
            raise ValueError("Graders already set for this assignment.")
        if not file.exists():
            raise FileNotFoundError(f"Graders file not found: {file}")

        with open(file, "r", encoding="utf-8") as f:
            self.graders = [line.strip() for line in f if line.strip()]
        return self

    def assign_graders_individual(self) -> Self:
        """Randomly assign graders to each student (idempotent if already assigned)."""
        if self._class_list is None or self._class_list.empty:
            raise ValueError(
                "No student data loaded. Call load_students() or set_students() first.")
        if not self.graders:
            raise ValueError(
                "No graders associated with this coursework. Set graders first.")

        df = self._class_list
        if "grader" in df.columns:
            log.info("Graders already assigned. Existing distribution retained.")
            return self

        n = len(df)
        df = df.copy()
        df.insert(
            len(df.columns),  # append at end
            "grader",
            pd.Series(
                np.random.permutation(
                    np.tile(self.graders, int(
                        np.ceil(n / max(len(self.graders), 1))))
                )[:n],
                index=df.index,
            ),
        )
        self._class_list = df
        return self

    # ---------- Misc ----------
    def toggle_ready(self) -> Self:
        self.ready = not self.ready
 self
