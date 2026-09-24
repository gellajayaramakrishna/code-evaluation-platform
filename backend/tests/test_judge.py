from app.judge import outputs_equal, classify, overall_verdict, CaseResult
from app.sandbox import ExecResult


def test_whitespace_normalized():
    assert outputs_equal("1  2\n", "1 2")
    assert outputs_equal("1\n2\n", "1 2")
    assert not outputs_equal("1 2", "1 3")


def test_float_tolerance():
    assert outputs_equal("1.0000001", "1.0")
    assert not outputs_equal("1.1", "1.0")


def test_classify_accepted():
    r = ExecResult("1 2\n", "", 0, 12, 100, False)
    assert classify(r, "1 2", 256) == "Accepted"


def test_classify_wa():
    r = ExecResult("1 3\n", "", 0, 12, 100, False)
    assert classify(r, "1 2", 256) == "Wrong Answer"


def test_classify_tle():
    r = ExecResult("", "", -9, 2000, 0, True)
    assert classify(r, "1", 256) == "Time Limit Exceeded"


def test_classify_re():
    r = ExecResult("", "Traceback", 1, 10, 0, False)
    assert classify(r, "1", 256) == "Runtime Error"


def test_overall_prefers_worst():
    cases = [
        CaseResult(1, "Accepted", 1, 1, "", "", 10, True),
        CaseResult(2, "Wrong Answer", 1, 1, "", "", 0, False),
    ]
    assert overall_verdict(cases) == "Wrong Answer"
