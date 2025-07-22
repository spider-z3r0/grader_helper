#!usr/bin/env


from .Documents import GradeFile, Calendar, ClassList, HandBook
from .CourseWork import CourseWork, CourseWorkType
from dependencies import pl, BaseModel
from typing import Self


class Course(BaseModel):
    name: str
    code: str
    root: pl.Path
    model_leader: str
    year: str  # This will be in the format 20xx(xy)
    internal_moderator: str
    ready: bool
    handbook: HandBook
    coursework: CourseWork | list[CourseWork]
    departmental_gradefile: GradeFile
    classlist: ClassList
    completed: bool

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
