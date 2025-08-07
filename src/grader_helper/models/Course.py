#!/usr/bin/env python

from grader_helper.models.Documents import GradeFile, Calendar, ClassList, HandBook
from grader_helper.models.CourseWork import CourseWork, CourseWorkType
from grader_helper.dependencies import pl, BaseModel, model_validator
from typing import Self


class Course(BaseModel):
    """
    Model representing a taught module within the grading workflow.

    Required fields
    ---------------
    name : str
        Human readable course title.
    code : str
        Module identifier used in files and systems.
    root : pathlib.Path
        Directory containing course resources.
    module_leader : str
        Lead academic for the module.
    year : str
        Academic year for the course (e.g. "2024/25").

    Lifecycle
    ---------
    1. Instantiate :class:`Course` with the required fields.
    2. Attach supporting documents such as the handbook, class list and
       departmental grade file.
    3. Add one or more :class:`~grader_helper.models.CourseWork.CourseWork`
       instances via :meth:`set_coursework`.
    4. Mark each document and coursework item as ready.
    5. Finalise the course by calling :meth:`set_ready`.
    """

    name: str
    code: str
    root: pl.Path
    module_leader: str
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
        """Attach coursework items to the course.

        Parameters
        ----------
        cw : CourseWork | list[CourseWork]
            A single coursework instance or a list of instances to append.

        Returns
        -------
        Self
            The updated course instance.

        Raises
        ------
        TypeError
            If ``cw`` is not a :class:`CourseWork` instance or a list of
            :class:`CourseWork` instances.
        """

        if not isinstance(self.coursework, list):
            self.coursework = [] if self.coursework is None else [self.coursework]

        if isinstance(cw, CourseWork):
            self.coursework.append(cw)
        elif isinstance(cw, list) and all(isinstance(i, CourseWork) for i in cw):
            self.coursework.extend(cw)
        else:
            raise TypeError(
                "'cw' must be a CourseWork instance or a list of CourseWork instances."
            )

        return self

    def set_ready(self) -> Self:
        """Mark the course as ready once all components are confirmed ready.

        Returns
        -------
        Self
            The updated course instance.

        Raises
        ------
        TypeError
            If any dependent document or coursework item has not been
            marked as ready via its ``toggle_ready`` method.
        """

        if not self.classlist.ready:
            raise TypeError(
                "Class list is not marked as ready. Call `toggle_ready()` on the class list when it is complete."
            )

        if not self.departmental_gradefile.ready:
            raise TypeError(
                "Departmental grade file is not marked as ready. Call `toggle_ready()` on the grade file when it is complete."
            )

        if isinstance(self.coursework, CourseWork):
            if not self.coursework.ready:
                raise TypeError(
                    f"Coursework '{self.coursework.name}' is not marked as ready. Call `toggle_ready()` on the coursework when it is complete."
                )
        elif isinstance(self.coursework, list):
            for cw in self.coursework:
                if not cw.ready:
                    raise TypeError(
                        f"Coursework '{cw.name}' is not marked as ready. Call `toggle_ready()` on the coursework when it is complete."
                    )

        if not self.handbook.ready:
            raise TypeError(
                "Handbook is not marked as ready. Call `toggle_ready()` on the handbook when it is complete."
            )

        # All checks passed – toggle course ready status
        self.ready = True
        return self
