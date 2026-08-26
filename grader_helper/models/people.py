#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""People involved in running a module.

One model serves the module leader, the internal moderator and the graders.
They are all just people; what differs is the role they are referenced from.
Holding them as a model rather than a bare string means a grader can later
be emailed their pack without introducing a new type.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer


class Person(BaseModel):
    """Someone who runs or marks part of a module.

    ``initials`` is the identity that appears in the machinery -- grader
    workbooks are named for it (``KOM.xlsx``) and the allocation column
    holds it -- so it is the field that must be stable and unique. The rest
    is contact detail.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    initials: str = Field(min_length=1)
    name: str | None = None
    email: str | None = None
    office: str | None = None

    @field_validator("initials")
    @classmethod
    def _upper(cls, value: str) -> str:
        """Initials are compared against filenames, so fix the case once."""
        return value.upper()

    @model_serializer
    def _serialize(self) -> "str | dict[str, str]":
        """Round-trip the shorthand.

        Someone who wrote ``graders = ["KOM", "SOB"]`` should get that back
        after a save, not have it rewritten into a block of
        ``[[assessment.graders]]`` tables. So a person carrying nothing but
        initials serialises as the bare string.
        """
        extra = {
            key: value
            for key, value in (
                ("name", self.name),
                ("email", self.email),
                ("office", self.office),
            )
            if value is not None
        }
        if not extra:
            return self.initials
        return {"initials": self.initials, **extra}

    def __str__(self) -> str:
        return self.name or self.initials


def as_person(value: "Person | str | dict") -> Person:
    """Coerce shorthand into a Person.

    The TOML may name a grader in full::

        [[assessment.graders]]
        initials = "KOM"
        name = "Kevin O Malley"

    or, far more often, just by initials::

        graders = ["KOM", "SOB"]

    Both are accepted; the short form is the one people actually write.
    """
    if isinstance(value, Person):
        return value
    if isinstance(value, str):
        return Person(initials=value)
    if isinstance(value, dict):
        return Person(**value)
    raise TypeError(
        f"Cannot read {value!r} as a person. Give either the initials as a "
        'string, or a table with at least initials = "..."'
    )
