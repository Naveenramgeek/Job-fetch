import app.repos.admin_repo as ar


class _Query:
    def __init__(self, value):
        self.value = value

    def filter(self, *args, **kwargs):
        return self

    def scalar(self):
        return self.value


class _DB:
    def __init__(self):
        self.values = iter([10, 9, 50, 30, 4, 2])

    def query(self, *args, **kwargs):
        return _Query(next(self.values))


def test_get_stats_returns_expected_shape():
    out = ar.get_stats(_DB())
    assert out == {
        "users_total": 10,
        "users_active": 9,
        "job_listings": 50,
        "user_job_matches": 30,
        "categories": 4,
        "admins": 2,
    }
