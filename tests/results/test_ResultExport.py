import unittest

from edsl.results import Results


class TestResultsExport(unittest.TestCase):

    def setUp(self):
        self.r = Results.example()

    def test_print(self):
        self.r.print(format="rich")
        self.r.print(format="html")
        self.r.print(format="markdown")

    # def test_bad_name(self):
    #     with pytest.raises(ValueError):
    #         self.r.print(format="bad")


if __name__ == "__main__":
    unittest.main()
