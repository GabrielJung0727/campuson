"""성능 테스트 — Locust 부하 테스트 설정 (v0.9).

사용법:
    pip install locust
    locust -f tests/performance/locustfile.py --host http://localhost:8000

웹 UI: http://localhost:8089
"""

from locust import HttpUser, between, task


class StudentUser(HttpUser):
    """학생 역할 부하 테스트 시나리오."""

    wait_time = between(1, 3)
    access_token: str = ""

    def on_start(self):
        """로그인하여 토큰 획득."""
        res = self.client.post("/api/v1/auth/login", json={
            "email": "loadtest_student@test.com",
            "password": "Password1",
        })
        if res.status_code == 200:
            self.access_token = res.json()["access_token"]
        else:
            # 계정 생성 후 재시도
            self.client.post("/api/v1/auth/register", json={
                "email": "loadtest_student@test.com",
                "password": "Password1",
                "name": "부하테스트",
                "department": "NURSING",
                "role": "STUDENT",
                "student_no": "LT001",
            })
            res = self.client.post("/api/v1/auth/login", json={
                "email": "loadtest_student@test.com",
                "password": "Password1",
            })
            if res.status_code == 200:
                self.access_token = res.json()["access_token"]

    @property
    def auth_headers(self):
        return {"Authorization": f"Bearer {self.access_token}"}

    @task(5)
    def get_me(self):
        self.client.get("/api/v1/users/me", headers=self.auth_headers)

    @task(3)
    def search_questions(self):
        self.client.get(
            "/api/v1/questions?department=NURSING&limit=10",
            headers=self.auth_headers,
        )

    @task(2)
    def get_my_history(self):
        self.client.get(
            "/api/v1/history/me?limit=20",
            headers=self.auth_headers,
        )

    @task(2)
    def get_calendar(self):
        self.client.get("/api/v1/calendar/events", headers=self.auth_headers)

    @task(1)
    def get_stats(self):
        self.client.get("/api/v1/history/stats", headers=self.auth_headers)

    @task(1)
    def health_check(self):
        self.client.get("/api/v1/health")


class ProfessorUser(HttpUser):
    """교수 역할 부하 테스트 시나리오."""

    wait_time = between(2, 5)
    access_token: str = ""

    def on_start(self):
        self.client.post("/api/v1/auth/register", json={
            "email": "loadtest_prof@test.com",
            "password": "Password1",
            "name": "부하교수",
            "department": "NURSING",
            "role": "PROFESSOR",
        })
        res = self.client.post("/api/v1/auth/login", json={
            "email": "loadtest_prof@test.com",
            "password": "Password1",
        })
        if res.status_code == 200:
            self.access_token = res.json()["access_token"]

    @property
    def auth_headers(self):
        return {"Authorization": f"Bearer {self.access_token}"}

    @task(3)
    def get_classes(self):
        self.client.get("/api/v1/classes", headers=self.auth_headers)

    @task(2)
    def get_reports(self):
        self.client.get("/api/v1/reports/compare", headers=self.auth_headers)

    @task(1)
    def get_osce_exams(self):
        self.client.get(
            "/api/v1/osce/exams?department=NURSING",
            headers=self.auth_headers,
        )
