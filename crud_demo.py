from app import app
from extensions import db
from models import Group, CheckerCode
from utils import create_key


text = """
flake8|F401
pylint|W0611
vulture|VU1327
flake8|F401
pylint|W0611
flake8|F403
flake8|F401
pylint|W0401
pylint|W0614
mypy|MY1489
flake8|F403
flake8|F401
pylint|W0401
pylint|W0614
mypy|MY1489
flake8|MN004
flake8|F401
pylint|C0411
vulture|VU1327
flake8|E501
bandit|B608
vulture|E501
flake8|MN001
flake8|MN001
pylint|W1514
pylint|R1732
flake8|E501
pylint|C0301
vulture|E501
bandit|B403
bandit|B404
bandit|B105
vulture|VU1498
bandit|B608
bandit|B307
pylint|W0123
bandit|B301
bandit|B602
pylint|C0115
pylint|C0116
pylint|C0116
pylint|C0116
pylint|C0116
pylint|C0116
pylint|C0116
pylint|C0116
pylint|C0116
pylint|E0606
pylint|C0116
pylint|C0116
vulture|VU1530
pylint|C0116
vulture|VU1530
pylint|C0116
vulture|VU1530
pylint|C0116
pylint|C0116
pylint|C0116
pylint|C0116
pylint|W0718
pylint|C0116
pylint|R0914
pylint|R0915
pylint|W0718
pylint|W0718
pylint|C0114
mypy|MY1489
pylint|C0116
pylint|W0718
pylint|C0116
pylint|C0116
pylint|C0116
pylint|C0116
pylint|C0116
mypy|MY1489
mypy|MY1181
mypy|MY1181
mypy|MY1489
mypy|MY1489
mypy|MY1489
mypy|MY1207
pylint|C0114
mypy|MY1489
pylint|C0116
pylint|W0718
pylint|C0116
pylint|C0116
pylint|C0116
pylint|C0116
pylint|C0116
mypy|MY1489
mypy|MY1181
mypy|MY1181
mypy|MY1489
mypy|MY1489
mypy|MY1489
mypy|MY1207
"""

with app.app_context():
    db.create_all()


lineset = set()
for line in text.splitlines():
    if not line:
        continue
    lineset.add(line)


with app.app_context():
    for line in lineset:
        checker, code = line.split("|")
        cc_obj = CheckerCode.query.filter_by(checker=checker, code=code).first()
        if cc_obj:
            continue
        checker_code2 = CheckerCode.create(
            checker=checker,
            code=code,
            group_key=create_key(checker, code),
            group_color="warning",
            group_name="Line too long",
            group_translate="lint.line_too_long",
        )

with app.app_context():
    # cc_qs = CheckerCode.query.filter_by(checker='mypy').all()
    # print(cc_qs)

    # cc_list = [
    #     {'checker': 'pylint', 'code': 'C0411'},
    #     {'checker': 'flake8', 'code': 'MN001'},
    #     {'checker': 'mypy', 'code': 'MY1207'},
    # ]
    # CheckerCode.in_group(cc_list)

    # obj = CheckerCode.query.filter_by(checker='flake8', code='MN001').first()
    # res = Group.split(obj.group_key)
    # print(res)

    Group.union(
        [
            "c4ce5c546ae4192474e9893167d231f2",
            "d9319807459f9ed5d3073acc39aefc0a",
            "8cfb08d53c3ba6b38ca2d20715df174f",
        ]
    )
