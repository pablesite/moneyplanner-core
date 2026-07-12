from datetime import date


RETIREMENT_AGE = 67


def date_at_age(birth_date: date, age: int = RETIREMENT_AGE) -> date:
    """Return the birthday at ``age``, keeping leap-day births valid."""
    try:
        return birth_date.replace(year=birth_date.year + age)
    except ValueError:
        return birth_date.replace(year=birth_date.year + age, day=28)
