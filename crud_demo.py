from app import app
from extensions import db
from models import Group, CheckerCode


def commit_or_rollback(action_name: str):
    try:
        db.session.commit()
        print(f"[OK] {action_name}")
    except Exception as e:
        db.session.rollback()
        print(f"[FAIL] {action_name}: {e}")


def create_demo_data():
    Group.get_or_create(
        "security",
        color="danger",
        name="Security",
        translate="Безопасность",
        descriptions="Demo group",
        is_hide=False,
    )

    Group.get_or_create(
        "network",
        color="dark",
        name="Network",
        translate="Сеть",
        descriptions="Another demo group",
        is_hide=False,
    )

    CheckerCode.get_or_create("bandit", "B101", group_key="security")
    CheckerCode.get_or_create("bandit", "B102", group_key="network")
    CheckerCode.get_or_create("flake8", "F401", group_key="network")

    commit_or_rollback("create_demo_data")


def read_demo_data():
    print("\nGroups:")
    for group in Group.query.order_by(Group.id).all():
        print(group.to_dict())

    print("\nChecker codes:")
    for item in CheckerCode.query.order_by(CheckerCode.id).all():
        print(item.to_dict())


def demo_grouping():
    print("\n--- Группировка ---")
    ids = CheckerCode.group_this(
        [("bandit", "B101"), ("bandit", "B102"), ("flake8", "F401")]
    )
    commit_or_rollback(f"group_this -> ids: {ids}")
    return ids


def demo_ungrouping(group_key: str):
    print(f"\n--- Разгруппировка группы {group_key} ---")
    ids = CheckerCode.ungroup_this(group_key)
    commit_or_rollback(f"ungroup_this -> ids: {ids}")
    return ids


def main():
    with app.app_context():
        db.create_all()

        print("=== 1. CREATE DEMO DATA ===")
        create_demo_data()
        read_demo_data()

        print("\n=== 2. GROUPING ===")
        demo_grouping()
        read_demo_data()

        first_item = CheckerCode.query.order_by(CheckerCode.id).first()
        if first_item:
            main_group_key = first_item.group_key
            print(f"\nОбъединённая группа: {main_group_key}")

            print("\n=== 3. UNGROUPING ===")
            demo_ungrouping(main_group_key)
            read_demo_data()
        else:
            print("\nНет объектов для разгруппировки.")


if __name__ == "__main__":
    main()
