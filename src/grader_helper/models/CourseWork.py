#!/usr/bin/env python

from enum import Enum
from typing import Self
from grader_helper.dependencies import (
    BaseModel, ConfigDict, pl, datetime, PositiveFloat,
    PrivateAttr, pd, np, log
)
from grader_helper.helpers import path_catcher


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
    grades_file: pl.Path | None = None  # persisted path only
    _grades_sheet: pd.DataFrame | None = PrivateAttr(
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
        suffix = self.class_list_path.suffix.lower()
        if suffix not in ['.csv', '.xlsx']:
            raise ValueError(
                f"Expected an Excel (.xlsx) or .csv class list, got {
                    suffix!r}."
            )

        try:
            if suffix == '.xlsx':
                df = pd.read_excel(self.class_list_path)
            else:
                df = pd.read_csv(self.class_list_path)
        except Exception as e:  # pragma: no cover
            raise RuntimeError(f"Failed to read class list file."
                               f"\n{e}") from e

        self._class_list = df
        return self

    def create_grades_sheet(self) -> Self:
        if self._class_list is None or self._class_list.empty:
            raise ValueError(
                    "The class list must be available in order to create a grading sheet for this assignment. "
                    "Please run the load_class list method, and then rerun this method."
            )

        # 1. Make a copy of the _class_list df
        df = self._class_list.copy()
        # 1.5. Drop the columns we don't want and rename some of the columns we do
        df = df.drop(columns=['End-of-Line Indicator', "OrgDefinedId"])
        df = df.rename({"Username": "Student ID"}, axis=1)
        # 2. Normalise the columns
        df.columns = [i.strip().lower().replace(' ', '_') for i in df.columns]
        # Check if the assignment name is in the _class_list.columns
        if not self.name.lower().replace(' ', '_') in any(self._class_list.columns):
            # Add a score column if it isn't
            df["score"] = 0
        else:
            # Rename the column that contains self.name
            df.rename({
                      [i for i in df.columns if i.contains(self.name.lower().replace(' ', '_')][0]: 'score'
            }, axis= 1)

        # 4. Reindex the columns
        df=df.reindex(columns=['student_id', 'score'])


        self._grades_sheet=df

        return self


    # ---------- Admin operations ----------

    def set_graders_from_txt(self, file: pl.Path) -> Self:
        """Load graders from a text file (one name per line)."""
        if self.graders:  # already set
            raise ValueError("Graders already set for this assignment.")
        if not file.exists():
            raise FileNotFoundError(f"Graders file not found: {file}")

        with open(file, "r", encoding="utf-8") as f:
            self.graders=[line.strip() for line in f if line.strip()]
        return self

    def assign_graders_individual(self) -> Self:
        """Randomly assign graders to each student (idempotent if already assigned)."""
        if self._class_list is None or self._class_list.empty:
            raise ValueError(
                "No student data loaded. Call load_students() or set_students() first.")
        if not self.graders:
            raise ValueError(
                "No graders associated with this coursework. Set graders first.")

        df=self._class_list
        if "grader" in df.columns:
            log.info("Graders already assigned. Existing distribution retained.")
            return self

        n=len(df)
        df=df.copy()
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
        self._grades_sheet=df
        return self

    def save_grades_sheets(self) -> Self:
        if self._grades_sheet is None or self._grades_sheet.empty:
            raise ValueError(
                    "The grades_sheet must be available in order to save a/the grading sheet(s) for this assignment. "
                    "Please run the create_grades_sheet method, and then rerun this method."
            )
        if self.graders is not None and 'grader' not in self_grades_sheet.columns:
            raise ValueError(
                    "It appears that graders have not been assigned to the students for this piece of CourseWork. "
                    "If you are grading this CourseWork on your own please clear the 'graders' field before running this again."
            )

        if self.graders is None and 'grader' not in self._grades_sheet.columns:
            try:
                if (self.root / f"grades.csv").exists():
                    choice=input(
                        f"grades.csv already exists. Do you want to overwrite it? (y/n): "
                    )
                    if choice[0].lower() != "y" or choice == "":
                        print(f"Skipping writing")
                        continue
                else:
                    self._grades_sheet.to_csv(
                        self.root/"grades.csv", index=False)
            except Exception as e:
                raise RunktimeError(
                        "Could not save grades sheet. "
                ) from e
        elif "grader" in self._grades_sheet.columns:
            try:
                # Loop over each grader
                for g in self.graders:
                    if (folder / f"{g}.xlsx").exists():
                        choice=input(
                            f"{g}.xlsx already exists. Do you want to overwrite it? (y/n): "
                        )
                        if choice[0].lower() != "y" or choice == "":
                            print(f"Skipping {g}.xlsx")
                            continue
                        else:
                            # Select the submissions assigned to the current grader
                            grader_submissions=d.loc[d["grader"] == f"{g}"]
                            # Save the submissions to an csv sheet
                            grader_submissions.to_csv(
                                self.root / f"{g}.csv", index=False)
                    else:
                        # Select the submissions assigned to the current grader
                        grader_submissions=d.loc[d["grader"] == f"{g}"]
                        # Save the submissions to an Excel sheet
                        grader_submissions.to_csv(
                            folder / f"{g}.csv", index=False)
            except Exception as e:
                print(f"An error occurred: {e}")






    # ---------- Misc ----------
    def toggle_ready(self) -> Self:
        self.ready=not self.ready
 self
