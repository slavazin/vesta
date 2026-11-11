"""The engine's version and the highest folder schema it reads."""
ENGINE = "0.3.0"
SCHEMA = 1


def parse(text):
    """`MAJOR.MINOR.PATCH` as a tuple of integers, for comparison."""
    return tuple(int(part) for part in text.strip().split("."))
