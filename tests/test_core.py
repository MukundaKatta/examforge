"""Tests for Examforge."""
from src.core import Examforge
def test_init(): assert Examforge().get_stats()["ops"] == 0
def test_op(): c = Examforge(); c.generate(x=1); assert c.get_stats()["ops"] == 1
def test_multi(): c = Examforge(); [c.generate() for _ in range(5)]; assert c.get_stats()["ops"] == 5
def test_reset(): c = Examforge(); c.generate(); c.reset(); assert c.get_stats()["ops"] == 0
def test_service_name(): c = Examforge(); r = c.generate(); assert r["service"] == "examforge"
