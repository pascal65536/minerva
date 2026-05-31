import uuid
from extensions import db


class Group(db.Model):
    __tablename__ = "groups"

    id = db.Column(db.Integer, primary_key=True)
    group_key = db.Column(db.String(64), unique=True, nullable=False, index=True)
    color = db.Column(db.String(32), nullable=False, default="info")
    name = db.Column(db.String(128), nullable=True)
    translate = db.Column(db.String(128), nullable=True)
    descriptions = db.Column(db.Text, nullable=True)
    is_hide = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<Group {self.group_key}: {self.name or 'unnamed'}>"

    def to_dict(self):
        return {
            "id": self.id,
            "group_key": self.group_key,
            "color": self.color,
            "name": self.name,
            "translate": self.translate,
            "descriptions": self.descriptions,
            "is_hide": self.is_hide,
        }

    @classmethod
    def get_or_create(cls, group_key, **defaults):
        obj = cls.query.filter_by(group_key=group_key).first()
        if obj is None:
            obj = cls(group_key=group_key, **defaults)
            db.session.add(obj)
        return obj


class CheckerCode(db.Model):
    __tablename__ = "checker_code"

    id = db.Column(db.Integer, primary_key=True)
    checker = db.Column(db.String(64), nullable=False, index=True)
    code = db.Column(db.String(32), nullable=False, index=True)
    group_key = db.Column(db.String(64), nullable=False, index=True)

    __table_args__ = (db.UniqueConstraint("checker", "code", name="uq_checker_code"),)

    def __repr__(self):
        return f"<CheckerCode {self.id}: {self.checker}:{self.code} {self.group_key}>"

    @property
    def color(self):
        group = Group.query.filter_by(group_key=self.group_key).first()
        return group.color if group else "info"

    @property
    def group_params(self):
        group = Group.query.filter_by(group_key=self.group_key).first()
        return group.to_dict() if group else {}

    def to_dict(self):
        return {
            "id": self.id,
            "checker": self.checker,
            "code": self.code,
            "group_key": self.group_key,
            "color": self.color,
            "params": self.group_params,
        }

    @classmethod
    def get_or_create(cls, checker, code, group_key=None):
        obj = cls.query.filter_by(checker=checker, code=code).first()
        if obj is None:
            if group_key is None:
                group_key = uuid.uuid4().hex
            obj = cls(checker=checker, code=code, group_key=group_key)
            db.session.add(obj)
            Group.get_or_create(group_key)
        return obj

    @classmethod
    def group_this(cls, checker_code_lst: list):
        """
        Объединяет несколько объектов CheckerCode в одну группу.
        Первый элемент в списке — главный, его group_key сохраняется (или создаётся новый, если нет).
        Данные из старых групп сливаются в главную.
        """
        if not checker_code_lst:
            return []

        first_checker, first_code = checker_code_lst[0]
        main_obj = cls.get_or_create(first_checker, first_code)
        main_key = main_obj.group_key or uuid.uuid4().hex

        ids = []
        group_keys = set()

        main_group = Group.query.filter_by(group_key=main_key).first()
        if main_group is None:
            main_group = Group(group_key=main_key)
            db.session.add(main_group)
            db.session.flush()

        for checker, code in checker_code_lst:
            obj = cls.get_or_create(checker, code)
            ids.append(obj.id)

            old_key = obj.group_key
            if old_key:
                group_keys.add(old_key)
                if old_key != main_key:
                    old_group = Group.query.filter_by(group_key=old_key).first()
                    if old_group:
                        cls._merge_group_data(main_group, old_group)

            obj.group_key = main_key

        db.session.flush()

        cls.query.filter(cls.id.in_(ids)).update(
            {cls.group_key: main_key},
            synchronize_session=False
        )

        unused_keys = group_keys - {main_key}
        if unused_keys:
            Group.query.filter(Group.group_key.in_(unused_keys)).delete(
                synchronize_session=False
            )

        Group.get_or_create(main_key)
        return ids

    @classmethod
    def ungroup_this(cls, group_key: str):
        """
        Разгруппировка всех объектов CheckerCode с данным group_key:
          - первый объект (по id) остаётся в исходной группе group_key;
          - для остальных каждый объект получает свою новую группу с копированием данных из старой группы.
        Возвращает список id объектов (включая первый).
        """
        objects = cls.query.filter_by(group_key=group_key).order_by(cls.id).all()
        if not objects:
            return []

        old_group = Group.query.filter_by(group_key=group_key).first()
        ids = []

        for i, obj in enumerate(objects):
            ids.append(obj.id)

            # Первый объект оставляем в старой группе
            if i == 0:
                continue

            # Создаём новую группу для этого объекта, копируя данные из старой
            new_key = uuid.uuid4().hex
            new_group = Group(
                group_key=new_key,
                color=old_group.color if old_group else "info",
                name=old_group.name,
                translate=old_group.translate,
                descriptions=old_group.descriptions,
                is_hide=old_group.is_hide,
            )
            db.session.add(new_group)

            obj.group_key = new_key

        db.session.flush()
        return ids

    @classmethod
    def _merge_group_data(cls, main_group, old_group):
        if not main_group.name and old_group.name:
            main_group.name = old_group.name
        if not main_group.descriptions and old_group.descriptions:
            main_group.descriptions = old_group.descriptions