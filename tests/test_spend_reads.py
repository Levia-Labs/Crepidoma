import pytest
import spend_parse


@pytest.mark.parametrize(
    ("command", "files"),
    [
        ("cat a.txt b.txt", ["a.txt", "b.txt"]),
        ("cat a.txt\nls\ngit status", ["a.txt"]),
        ("cat a.txt | grep x", ["a.txt"]),
        ("cat a.txt|grep x", ["a.txt"]),
        ("cat a.txt; task lint", ["a.txt"]),
        ("head -n 5 a.txt && git log", ["a.txt"]),
        ("sed -n 1,5p a.txt", ["a.txt"]),
        ("git log", []),
    ],
)
def test_bash_read_files_excludes_command_names(command, files):
    assert spend_parse.bash_read_files(command) == files
