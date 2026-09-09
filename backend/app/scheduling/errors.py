class SchedulingError(Exception):
    code = "SCHEDULING_ERROR"


class SchedulingInputInvalid(SchedulingError):
    code = "SCHEDULING_INPUT_INVALID"


class SchedulingInfeasible(SchedulingError):
    code = "SCHEDULING_INFEASIBLE"
