"""Reference correct solution for the semver fixture — used ONLY to prove the task is
solvable (Layer-1 self-test applies it and asserts all tests pass). It is NOT placed in any
agent's workspace. Implements all four precedence rules from src/semver.py's docstring."""


def _parse(v):
    core = v.partition("+")[0]              # rule 4: drop build metadata
    core_part, _, pre = core.partition("-")
    nums = [int(x) for x in core_part.split(".")]
    pre_ids = pre.split(".") if pre else []
    return nums, pre_ids


def _cmp_pre_id(x, y):
    xn, yn = x.isdigit(), y.isdigit()
    if xn and yn:
        ix, iy = int(x), int(y)
        return (ix > iy) - (ix < iy)        # numeric compare numerically
    if xn and not yn:
        return -1                            # numeric < alphanumeric
    if yn and not xn:
        return 1
    return (x > y) - (x < y)                 # ASCII order


def compare(a, b):
    na, pa = _parse(a)
    nb, pb = _parse(b)
    if na != nb:                             # rule 1
        return (na > nb) - (na < nb)
    if not pa and pb:                        # rule 2
        return 1
    if pa and not pb:
        return -1
    if not pa and not pb:
        return 0
    for x, y in zip(pa, pb):                 # rule 3
        c = _cmp_pre_id(x, y)
        if c != 0:
            return c
    return (len(pa) > len(pb)) - (len(pa) < len(pb))
