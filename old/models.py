from extensions import db
from utils import create_key
import os
import logging

os.makedirs("log", exist_ok=True)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
h = logging.FileHandler("log/app.log", encoding="utf-8")
h.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(message)s"))
logger.addHandler(h)


class Group(db.Model):
    __tablename__ = "groups"

    id = db.Column(db.Integer, primary_key=True)
    group_key = db.Column(db.String(32), unique=True, nullable=False, index=True)
    color = db.Column(db.String(32), nullable=False, default="info")
    name = db.Column(db.String(128), nullable=True)
    translate = db.Column(db.String(128), nullable=True)
    descriptions = db.Column(db.Text, nullable=True)
    is_hide = db.Column(db.Boolean, default=False)
    source_url = db.Column(db.String(512), nullable=True)
    best_practice = db.Column(db.Text, nullable=True)

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
            "source_url": self.source_url,
            "best_practice": self.best_practice,
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
        source_url=None,
        best_practice=None,
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
                source_url=source_url,
                best_practice=best_practice,
            )
            db.session.add(group)
            db.session.commit()
        return group

    @classmethod
    def split(cls, group_key):
        obj = cls.query.filter_by(group_key=group_key).first()
        logger.info(f"[SPLIT] Начало разгруппировки для key={group_key}, obj={obj}")
        if not obj:
            raise ValueError(f"Group '{group_key}' not found")

        cc_qs = CheckerCode.query.filter_by(group_key=group_key).all()
        logger.info(f"[SPLIT] Найдено CheckerCode: {len(cc_qs)} шт")
        result = [obj]

        for cc in cc_qs:
            this_group_key = create_key(cc.checker, cc.code)
            logger.info(
                f"[SPLIT] CheckerCode checker={cc.checker} code={cc.code} -> this_group_key={this_group_key}"
            )

            if group_key == this_group_key:
                continue

            cc.group_key = this_group_key

            group = cls.get_or_create(
                group_key=this_group_key,
                color=obj.color,
                name=obj.name,
                translate=obj.translate,
                descriptions=obj.descriptions,
                is_hide=obj.is_hide,
                source_url=obj.source_url,
                best_practice=obj.best_practice,
            )
            logger.info(
                f"[SPLIT] Создана/получена группа: group_key={group.group_key} is_hide={group.is_hide}"
            )
            result.append(group)

        db.session.commit()
        logger.info(f"[SPLIT] Завершено. Всего групп в результате: {len(result)}")
        for g in result:
            logger.info(f"[SPLIT] RESULT group_key={g.group_key} is_hide={g.is_hide}")
        return result

    @classmethod
    def union(cls, group_key_list):
        if not group_key_list:
            return None

        uniq_keys = list(dict.fromkeys(group_key_list))
        main_group_key = uniq_keys[0]
        main_group = cls.query.filter_by(group_key=main_group_key).first()

        if not main_group:
            raise ValueError(f"Group '{main_group_key}' not found")

        merge_groups = cls.query.filter(cls.group_key.in_(uniq_keys[1:])).all()
        merge_group_keys = [g.group_key for g in merge_groups]

        if not merge_groups:
            return main_group

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
            # Наследуем URL и Best Practice, если у главной группы их нет
            if not main_group.source_url and g.source_url:
                main_group.source_url = g.source_url
            if not main_group.best_practice and g.best_practice:
                main_group.best_practice = g.best_practice

        CheckerCode.query.filter(CheckerCode.group_key.in_(merge_group_keys)).update(
            {"group_key": main_group_key}, synchronize_session=False
        )
        db.session.add(main_group)
        db.session.flush()

        for g in merge_groups:
            db.session.delete(g)

        db.session.commit()
        return main_group


class CheckerCode(db.Model):
    __tablename__ = "checker_code"

    id = db.Column(db.Integer, primary_key=True)
    checker = db.Column(db.String(32), nullable=False, index=True)
    code = db.Column(db.String(32), nullable=False, index=True)
    group_key = db.Column(
        db.String(32), db.ForeignKey("groups.group_key"), nullable=False, index=True
    )
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
        group_source_url=None,
        group_best_practice=None,
        **kwargs,
    ):
        group = Group.get_or_create(
            group_key=group_key,
            color=group_color,
            name=group_name,
            translate=group_translate,
            descriptions=group_descriptions,
            is_hide=group_is_hide,
            source_url=group_source_url,
            best_practice=group_best_practice,
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

        for group_key in cc_group_key_lst:
            if group_key == first_obj.group_key:
                continue
            remaining_count = cls.query.filter_by(group_key=group_key).count()
            if remaining_count == 0:
                group = Group.query.filter_by(group_key=group_key).first()
                if group:
                    db.session.delete(group)
        db.session.commit()
        return result
