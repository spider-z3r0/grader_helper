#!/usr/bin/env python

from grader_helper.models.Documents import GradeFile, Calendar, ClassList, HandBook
from grader_helper.models.CourseWork import CourseWork, CourseWorkType
from grader_helper.dependencies import pl, BaseModel, model_validator
from typing import Self


class Course(BaseModel):
    name: str
    code: str
    root: pl.Path
    model_leader: str
    year: str  # This will be in the format 20xx(xy)
    internal_moderator: str | None = None
    ready: bool = False
    handbook: HandBook | None = None
    coursework: CourseWork | list[CourseWork] | None = None
    departmental_gradefile: GradeFile | None = None
    classlist: ClassList | None = None
    completed: bool = False

    @model_validator(mode='before')
    @classmethod
    def validate_coursework(cls, data: any) -> any:
        """
        Normalizes the 'coursework' field from raw input to ensure consistent internal structure.

        This validator intercepts the raw input data before model parsing, and ensures that the
        'coursework' field is always either a list of coursework items or None.

        Accepted formats:
        - A list of coursework items (ideal)
        - A single coursework item (dict), which will be wrapped in a list
        - Omission of the field, which will default to None

        Raises
        ------
        TypeError:
            If the input data is not a dictionary (e.g., the model was instantiated incorrectly).
        ValueError:
            If the 'coursework' field is present but not a list, a dict, or None (e.g., a string or int).
        """
        if not isinstance(data, dict):
            raise TypeError(
                "Course data must be provided as a Python dictionary. "
                "See the documentation for expected input formats and examples."
            )

        if "coursework" not in data:
            data["coursework"] = None

        if isinstance(data["coursework"], dict):
            data["coursework"] = [data["coursework"]]
        elif isinstance(data["coursework"], list):
            data["coursework"] = data["coursework"]
        elif data["coursework"] is not None:
            raise ValueError(
                f"Invalid format for 'coursework': expected a list of items or a single item as a dictionary. "
                f"Got type '{type(data['coursework']).__name__}' instead."
            )

        return data

    def set_coursework(self, cw: list[CourseWork] | CourseWork) -> Self:
        try:
            if not isinstance(self.coursework, list):
                self.coursework = [self.coursework]
            if isinstance(cw, CourseWork):
                self.coursework.append(cw)
            elif isinstance(cw, list):
                self.coursework.extend(cw)
        except Exception as e:
            raise e

    def set_ready(self) -> Self:
        if not self.classlist.ready:
            raise TypeError(
                "Classlist not marked as ready. Please double check and run `.toggle_ready()` on classlist if you are satisfied it is ready to go."
            )

        if not self.departmental_gradefile.ready:
            raise TypeError(
                "Departmental gradefile not marked as ready. Please check and toggle its status if appropriate."
            )

        if isinstance(self.coursework, CourseWork):
            if not self.coursework.ready:
                raise TypeError(
                    f"CourseWork '{self.coursework.name}' not marked as ready."
                )
        elif isinstance(self.coursework, list):
            for cw in self.coursework:
                if not cw.ready:
                    raise TypeError(
                        f"CourseWork '{cw.name}' not marked as ready."
                    )

        if not self.handbook.ready:
            raise TypeError(
                "Handbook not marked as ready. Please check and toggle its status if appropriate."
            )

        # All checks passed – toggle course ready status
        self.ready = True
        return self
