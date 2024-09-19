from src.toddgpt.tools.chemcloud_tool import FindJobExample
import pytest

frequency_input = """
run          initcond
basis        def2-svp
method       wb97xd3
charge       0
spinmult     1

coordinates  geom.xyz"""


@pytest.mark.parametrize(
    "job_name, expected",
    [
        ("initcond", frequency_input.strip()),
        ("nonexistent", "No example input found for job nonexistent"),
    ],
)
def test_find_job_example(job_name, expected):
    tool = FindJobExample()
    if job_name == "nonexistent":
        with pytest.raises(ValueError, match=expected):
            tool.find_job_example(job_name)
    else:
        result = tool.find_job_example(job_name)
        assert result == expected
