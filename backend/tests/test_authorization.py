"""Authorization tests.

These are the security-critical tests: a teacher must not reach another
teacher's subject or student, no matter what they put in the URL or the body.
"""
from __future__ import annotations

from app.core.security import SESSION_COOKIE, issue_session


class TestSession:
    def test_no_cookie_is_unauthorized(self, client):
        assert client.get("/api/teachers/me").status_code == 401

    def test_forged_cookie_is_rejected(self, client):
        client.cookies.set(SESSION_COOKIE, "TCH001")
        assert client.get("/api/teachers/me").status_code == 401

    def test_tampered_signature_is_rejected(self, client):
        token = issue_session("TCH001")
        client.cookies.set(SESSION_COOKIE, token[:-4] + "AAAA")
        assert client.get("/api/teachers/me").status_code == 401

    def test_cookie_for_unknown_teacher_is_rejected(self, client):
        client.cookies.set(SESSION_COOKIE, issue_session("TCH999"))
        assert client.get("/api/teachers/me").status_code == 401

    def test_session_resolves_scope_from_the_database(self, alpha):
        body = alpha.get("/api/teachers/me").json()
        assert body["teacher_id"] == "TCH001"
        assert sorted(body["subject_codes"]) == ["CB3202L", "CB3202T"]

    def test_unknown_teacher_cannot_create_a_session(self, client):
        r = client.post("/api/demo-session", json={"teacher_id": "TCH404"})
        assert r.status_code == 404

    def test_malformed_teacher_id_is_rejected(self, client):
        r = client.post("/api/demo-session", json={"teacher_id": "'; DROP TABLE--"})
        assert r.status_code == 422

    def test_logout_clears_access(self, alpha):
        assert alpha.get("/api/teachers/me").status_code == 200
        alpha.post("/api/auth/logout")
        alpha.cookies.clear()
        assert alpha.get("/api/teachers/me").status_code == 401

    def test_session_cookie_is_httponly(self, client):
        r = client.post("/api/demo-session", json={"teacher_id": "TCH001"})
        assert "httponly" in r.headers["set-cookie"].lower()


class TestSubjectScope:
    def test_own_subject_is_allowed(self, alpha):
        assert alpha.get("/api/subjects/CB3202T/attendance").status_code == 200

    def test_other_teachers_subject_is_denied(self, alpha):
        """CB3201T belongs to TCH002."""
        for path in [
            "/api/subjects/CB3201T/attendance",
            "/api/subjects/CB3201T/analytics",
            "/api/subjects/CB3201T/assessments",
            "/api/subjects/CB3201T/assignments",
            "/api/subjects/CB3201T/performance",
            "/api/subjects/CB3201T/attendance.csv",
        ]:
            assert alpha.get(path).status_code == 403, path

    def test_unassigned_subject_is_denied(self, alpha):
        """Nobody teaches CB3203T-A, so it is out of scope for everyone."""
        assert alpha.get("/api/subjects/CB3203T-A/attendance").status_code == 403

    def test_the_two_teachers_see_different_scopes(self, alpha, beta):
        assert alpha.get("/api/subjects/CB3202T/attendance").status_code == 200
        assert beta.get("/api/subjects/CB3202T/attendance").status_code == 403
        assert beta.get("/api/subjects/CB3201T/attendance").status_code == 200
        assert alpha.get("/api/subjects/CB3201T/attendance").status_code == 403

    def test_nonexistent_subject_does_not_leak_existence(self, alpha):
        """A fake code and a real-but-forbidden code give the same answer."""
        fake = alpha.get("/api/subjects/ZZ9999T/attendance").status_code
        real = alpha.get("/api/subjects/CB3201T/attendance").status_code
        assert fake == real == 403

    def test_malformed_subject_code_is_rejected(self, alpha):
        for bad in ["../../etc/passwd", "CB3202T'%20OR%201=1", "<script>"]:
            assert alpha.get(f"/api/subjects/{bad}/attendance").status_code in (403, 404, 422)

    def test_subject_filter_on_student_list_is_authorized(self, alpha):
        ok = alpha.get("/api/teachers/me/students?subject_code=CB3202T")
        assert ok.status_code == 200
        denied = alpha.get("/api/teachers/me/students?subject_code=CB3201T")
        assert denied.status_code == 403


class TestStudentScope:
    def test_student_in_scope_is_allowed(self, alpha):
        r = alpha.get("/api/students/STU0001/academic-summary")
        assert r.status_code == 200
        assert r.json()["student_id"] == "STU0001"

    def test_student_outside_scope_is_denied(self, alpha):
        """STU0004 is enrolled only in Beta's subject."""
        assert alpha.get("/api/students/STU0004/academic-summary").status_code == 403
        assert alpha.get("/api/students/STU0004/activities").status_code == 403

    def test_beta_can_reach_that_same_student(self, beta):
        assert beta.get("/api/students/STU0004/academic-summary").status_code == 200

    def test_nonexistent_student_is_denied_not_disclosed(self, alpha):
        assert alpha.get("/api/students/STU9999/academic-summary").status_code == 403

    def test_malformed_student_id_is_rejected(self, alpha):
        assert alpha.get("/api/students/XX01/academic-summary").status_code == 422

    def test_summary_contains_only_in_scope_subjects(self, alpha):
        body = alpha.get("/api/students/STU0001/academic-summary").json()
        codes = {row["subject_code"] for row in body["attendance"]}
        assert codes <= {"CB3202T", "CB3202L"}

    def test_student_list_excludes_out_of_scope_students(self, alpha):
        body = alpha.get("/api/teachers/me/students").json()
        ids = {s["student_id"] for s in body["items"]}
        assert "STU0004" not in ids
        assert {"STU0001", "STU0002", "STU0003"} <= ids


class TestCoordinatorRole:
    def test_coordinator_can_run_department_report(self, alpha):
        assert alpha.get("/api/department/extracurricular").status_code == 200

    def test_ordinary_teacher_cannot(self, beta):
        """Teaching one subject must not imply department-wide access."""
        assert beta.get("/api/department/extracurricular").status_code == 403

    def test_ordinary_teacher_still_gets_their_own_aggregate(self, beta):
        assert beta.get("/api/teachers/me/extracurricular").status_code == 200


class TestDataLeakage:
    def test_profile_omits_server_configuration(self, alpha):
        body = alpha.get("/api/teachers/me").json()
        blob = str(body).lower()
        for secret in ["password", "database_url", "session_secret", "postgres"]:
            assert secret not in blob

    def test_student_records_are_not_cacheable(self, alpha):
        r = alpha.get("/api/students/STU0001/academic-summary")
        assert "no-store" in r.headers.get("cache-control", "")

    def test_csv_export_respects_subject_scope(self, alpha):
        assert alpha.get("/api/subjects/CB3202T/attendance.csv").status_code == 200
        assert alpha.get("/api/subjects/CB3201T/attendance.csv").status_code == 403

    def test_csv_export_respects_active_filters(self, alpha):
        """The export must contain exactly the filtered rows, not the full table."""
        r = alpha.get("/api/subjects/CB3202T/attendance.csv?below_only=true")
        lines = [ln for ln in r.text.strip().splitlines() if ln]
        assert len(lines) == 2  # header + STU0003 only (62.5%)
        assert "STU0003" in r.text
        assert "STU0001" not in r.text
