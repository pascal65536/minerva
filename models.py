from extensions import db
from utils import create_key


class Group(db.Model):
    __tablename__ = "groups"

    id = db.Column(db.Integer, primary_key=True)
    group_key = db.Column(db.String(32), unique=True, nullable=False, index=True)
    color = db.Column(db.String(32), nullable=False, default="info")
    name = db.Column(db.String(128), nullable=True)
    translate = db.Column(db.String(128), nullable=True)
    descriptions = db.Column(db.Text, nullable=True)
    is_hide = db.Column(db.Boolean, default=False)

    checker_codes = db.relationship(
        "CheckerCode",
        backref="group_obj",
        lazy="dynamic",
        foreign_keys="CheckerCode.group_key",
    )

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
    def get_or_create(
        cls,
        group_key,
        color="info",
        name=None,
        translate=None,
        descriptions=None,
        is_hide=False,
    ):
        group = cls.query.filter_by(group_key=group_key).first()

        if not group:
            group = cls(
                group_key=group_key,
                color=color,
                name=name,
                translate=translate,
                descriptions=descriptions,
                is_hide=is_hide,
            )
            db.session.add(group)
            db.session.commit()

        return group

    @classmethod
    def split(cls, group_key):
        """
        Разбить группу на несколько новых групп.
        """
        # Получить исходную группу
        obj = cls.query.filter_by(group_key=group_key).first()

        if not obj:
            raise ValueError(f"Group '{group_key}' not found")

        cc_qs = CheckerCode.query.filter_by(group_key=group_key).all()

        result = list()
        result.append(obj)
        for cc in cc_qs:
            this_group_key = create_key(cc.checker, cc.code)
            if group_key == this_group_key:
                continue
            group = Group.get_or_create(
                group_key=this_group_key,
                color=obj.color,
                name=obj.name,
                translate=obj.translate,
                descriptions=obj.descriptions,
                is_hide=obj.is_hide,
            )
            result.append(group)
        db.session.commit()
        return result


    @classmethod
    def union(cls, group_key_list):
        """
        Объединить несколько групп в одну.

        Первый group_key в списке — главный.
        Все CheckerCode остальных групп переводятся в главный group_key.
        Данные объединяемых групп переносятся в главную группу.
        Остальные группы удаляются.

        Args:
            group_key_list: список group_key, например ["g1", "g2", "g3"]

        Returns:
            Group: главная группа
        """
        if not group_key_list:
            return None

        # Убираем дубликаты, сохраняя порядок
        uniq_keys = list(dict.fromkeys(group_key_list))
        main_group_key = uniq_keys[0]

        main_group = cls.query.filter_by(group_key=main_group_key).first()
        if not main_group:
            raise ValueError(f"Group '{main_group_key}' not found")

        merge_groups = cls.query.filter(cls.group_key.in_(uniq_keys[1:])).all()
        merge_group_keys = [g.group_key for g in merge_groups]

        if not merge_groups:
            return main_group

        # Переносим данные групп в главную
        for g in merge_groups:
            if not main_group.color or main_group.color == "info":
                main_group.color = g.color
            if not main_group.name and g.name:
                main_group.name = g.name
            if not main_group.translate and g.translate:
                main_group.translate = g.translate
            if not main_group.descriptions and g.descriptions:
                main_group.descriptions = g.descriptions
            if not main_group.is_hide and g.is_hide:
                main_group.is_hide = g.is_hide

        # Переводим все CheckerCode в главную группу
        CheckerCode.query.filter(
            CheckerCode.group_key.in_(merge_group_keys)
        ).update(
            {"group_key": main_group_key},
            synchronize_session=False
        )

        # Сохраняем изменения главной группы
        db.session.add(main_group)
        db.session.flush()

        # Удаляем объединяемые группы
        for g in merge_groups:
            db.session.delete(g)

        db.session.commit()
        return main_group



class CheckerCode(db.Model):
    __tablename__ = "checker_code"

    id = db.Column(db.Integer, primary_key=True)
    checker = db.Column(db.String(32), nullable=False, index=True)
    code = db.Column(db.String(32), nullable=False, index=True)
    group_key = db.Column(db.String(32), db.ForeignKey("groups.group_key"), nullable=False, index=True)

    __table_args__ = (db.UniqueConstraint("checker", "code", name="uq_checker_code"),)

    def __repr__(self):
        return f"<CheckerCode {self.id}: {self.checker}:{self.code} {self.group_key}>"

    def to_dict(self):
        return {
            "id": self.id,
            "checker": self.checker,
            "code": self.code,
            "group_key": self.group_key,
        }

    @classmethod
    def create(
        cls,
        checker,
        code,
        group_key,
        group_color="info",
        group_name=None,
        group_translate=None,
        group_descriptions=None,
        group_is_hide=False,
        **kwargs,
    ):
        """
        Создать CheckerCode, автоматически создав/получив Group.
        """
        group = Group.get_or_create(
            group_key=group_key,
            color=group_color,
            name=group_name,
            translate=group_translate,
            descriptions=group_descriptions,
            is_hide=group_is_hide,
        )

        default_dct = {
            "checker": checker,
            "code": code,
            "group_key": group.group_key,
        }
        checker_code = cls(**default_dct, **kwargs)
        db.session.add(checker_code)
        db.session.commit()
        return checker_code

    @classmethod
    def in_group(cls, cc_list):
        cc_group_key_lst = list()
        first_obj = None
        for cc in cc_list:
            obj = cls.query.filter_by(**cc).first()
            cc_group_key_lst.append(obj.group_key)
            if not first_obj:
                first_obj = obj

        if not cc_group_key_lst:
            return []

        result = cls.query.filter(cls.group_key.in_(cc_group_key_lst)).all()
        if not first_obj:
            first_obj = result[0]

        for r in result:
            if r == first_obj:
                continue
            r.group_key = first_obj.group_key
        db.session.commit()

        # Удаляем группы, которые теперь пустые (исключая target_group_key)
        for group_key in cc_group_key_lst:
            if group_key == first_obj.group_key:
                continue

            # Проверить, есть ли ещё CheckerCode с этим group_key
            remaining_count = cls.query.filter_by(group_key=group_key).count()

            if remaining_count == 0:
                # Удалить группу
                group = Group.query.filter_by(group_key=group_key).first()
                if group:
                    db.session.delete(group)
                    db.session.commit()

        return result


