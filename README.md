# diff-scrapper.py

Python web scrapper on GitLab API which allows to collect all changes from many repositories.

1) First searching recursively for subgroups.
2) Processing repositories from subgroup.
3) As a result in the same directory:
    a) create directory with name: <output_YYYY-MM-DD-HH:MM:SS>
    b) diffs will be saved in files with names: <YYYY-MM__repository_name__branch_name.patch>

## Steps to setup environment:
- `python -m venv env`
- `source env/bin/activate`
- `pip install -r requirements.txt`
- `python diff-scrapper.py --help`
- `deactivate`

## Contact

* kamkie1996@gmail.com