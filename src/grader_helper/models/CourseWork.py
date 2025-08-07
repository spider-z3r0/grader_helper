#!/usr/bin/env python


from enum import Enum
from typing import Self
from grader_helper.dependencies import (
    BaseModel, ConfigDict, pl, datetime, PositiveFloat, pd, np
)
from .Documents import ClassList, GradeFile, FileType


class CourseWorkType(Enum):
    Exam = 'exam'
    Assignment = 'assignment'
    Online_MCQ = 'online_mcq'
    InPerson_MCQ = 'inperson_mcq'


class CourseWork(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str
    root: pl.Path
    weight: PositiveFloat
    graders: list[str] = []
    students: pd.DataFrame | None = None
    type: CourseWorkType
    due_date: datetime.datetime
    rubric: pl.Path
    feedback_sheet: pl.Path
    ready: bool = False
    completed: bool = False

    def toggle_ready(self) -> Self:
        self.ready = not self.ready
        return self

    def set_graders(self, file: pl.Path) -> Self:
        """
        Loads a list of graders from a text file.

        Parameters
        ----------
        file : pathlib.Path
        The path to the text file containing the list of graders.

        Returns
        -------
        List[str]
        A list of graders.
        """
        if len(self.graders) != 0:
            raise ValueError("Graders already set for this assignment")
        with open(file, "r") as f:
            self.graders = [
                i.strip() for i in f.readlines() if i.strip()
            ]
        return self

    def set_students(
            self, file: GradeFile) -> Self:
        """
        Imports a dataframe of students from the Gradesfile exported from Brightspace.
        The 'file path' must be a feild in the

        Parameters
        ----------
        file : pathlib.Path
            The path to the CSV file containing the Brightspace classlist.
        assignment_name : str
            The name of the assignment.

        Returns
        -------
        pandas DataFrame
            The Brightspace classlist.
        """
        # Check if the file is a CSV file
        if file.type != FileType.XL:
            raise ValueError("File must be a .xlsx file.")

        try:

            classlist_df = pd.read_excel(file.path)

            classlist_df.columns = [str(i).lower().strip().replace(
                ' ', '_').replace('-', '_') for i in classlist_df.columns]

            classlist_df.insert(
                len(classlist_df.columns)-1,
                f"{self.name.lower().replace(' ', '_').strip()}",
                ''
            )
            # classlist_df.insert(
            #     -1,
            #     f"{self.name.lower().replace(' ', '_').strip()}",
            # '')
            self.students = classlist_df

            return self

        except Exception as e:
            print(f"Error occurred while importing Brightspace classlist: {e}")
            return None

    def assign_graders_individual(self):
        """
        Assigns graders randomly to students.

        Returns
        -------
        Self
            The updated object with graders assigned.
        """
        if self.students is None or self.students.empty:
            raise ValueError(
                "No student data loaded. Run self.set_students() first.")

        if "grader" in self.students.columns:
            print("Graders already assigned. Existing distribution retained.")
            return self

        if len(self.graders) < 1:
            raise ValueError("No graders associated with this coursework.")

        n_students = len(self.students)

        df = self.students.copy()
        df.insert(
            len(df.columns) - 2,
            "grader",
            pd.Series(
                np.random.permutation(
                    np.tile(self.graders, int(
                        np.ceil(n_students / len(self.graders))))
                )[:n_students],
                index=df.index
            )
        )

        self.students = df
        for i in self.students.columns:
            print(i)

        return self
