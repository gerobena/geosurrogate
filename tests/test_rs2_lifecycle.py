"""RS2 process lifecycle: an instance we started must never outlive the task.

Reported from a real from-zero run: after "detect materials" the RS2 window
stayed open holding port 60054, so training could not start until the user
closed it by hand; the same happened after training. Root cause: RS2Scripting's
closeProgram() raises TimeoutError when the app has not released the port within
30 s, and the adapter swallowed that silently. These tests pin the contract with
a fake RS2 - no real process is ever started.
"""

import geosurrogate.solvers.rs2 as rs2


class FakeApp:
    """Stands in for RS2Modeler / RS2Interpreter."""

    def __init__(self, fail: Exception | None = None):
        self.fail = fail
        self.close_calls = 0

    def closeProgram(self, save=None):  # noqa: N802 (RS2Scripting's spelling)
        self.close_calls += 1
        if self.fail is not None:
            raise self.fail


def test_close_app_reports_a_timeout_instead_of_hiding_it(capsys):
    app = FakeApp(fail=TimeoutError("did not close within the timeout"))
    rs2._close_app(app, "RS2 Modeler")
    out = capsys.readouterr().out
    assert app.close_calls == 1
    assert "did not close cleanly" in out, "a failed close must be visible"


def test_close_app_falls_back_to_the_old_signature():
    app = FakeApp(fail=TypeError("closeProgram() takes 1 positional argument"))
    rs2._close_app(app, "RS2 Modeler")
    # Called twice: once with the flag, once without after the TypeError.
    assert app.close_calls == 2


def test_reap_force_closes_only_the_pids_we_started(monkeypatch, capsys):
    monkeypatch.setattr(rs2, "_rs2_process_ids", lambda: {111, 222, 999})
    killed: list[set[int]] = []

    def fake_force_close(pids):
        killed.append(set(pids))
        return sorted(pids)

    monkeypatch.setattr(rs2, "_force_close", fake_force_close)
    rs2._reap({111, 222}, "RS2")

    assert killed == [{111, 222}], "999 is the user's own RS2 and must survive"
    assert "force-closed" in capsys.readouterr().out


def test_reap_is_silent_when_nothing_leaked(monkeypatch, capsys):
    monkeypatch.setattr(rs2, "_rs2_process_ids", lambda: {999})
    monkeypatch.setattr(rs2, "_force_close",
                        lambda pids: (_ for _ in ()).throw(AssertionError("must not kill")))
    rs2._reap({111}, "RS2")
    assert capsys.readouterr().out == ""


def test_reap_warns_when_a_leftover_cannot_be_killed(monkeypatch, capsys):
    monkeypatch.setattr(rs2, "_rs2_process_ids", lambda: {111})
    monkeypatch.setattr(rs2, "_force_close", lambda pids: [])
    rs2._reap({111}, "RS2")
    out = capsys.readouterr().out
    assert "still running" in out and "port is occupied" in out


def test_process_ids_is_a_set_and_safe_off_windows():
    assert isinstance(rs2._rs2_process_ids(), set)
