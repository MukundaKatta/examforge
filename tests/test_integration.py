"""Integration tests for Examforge."""
from src.core import Examforge

class TestExamforge:
    def setup_method(self):
        self.c = Examforge()
    def test_10_ops(self):
        for i in range(10): self.c.generate(i=i)
        assert self.c.get_stats()["ops"] == 10
    def test_service_name(self):
        assert self.c.generate()["service"] == "examforge"
    def test_different_inputs(self):
        self.c.generate(type="a"); self.c.generate(type="b")
        assert self.c.get_stats()["ops"] == 2
    def test_config(self):
        c = Examforge(config={"debug": True})
        assert c.config["debug"] is True
    def test_empty_call(self):
        assert self.c.generate()["ok"] is True
    def test_large_batch(self):
        for _ in range(100): self.c.generate()
        assert self.c.get_stats()["ops"] == 100
