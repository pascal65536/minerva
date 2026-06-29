import os
import uuid
import time
import logging
import json
from extensions import db
from utils import create_key

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
    color = db.Column(db.String(32), nullable=False, default="primary")
    name = db.Column(db.String(128), nullable=True)
    translate = db.Column(db.String(128), nullable=True)
    descriptions = db.Column(db.Text, nullable=True)
    is_hide = db.Column(db.Boolean, default=False)
    source_url = db.Column(db.String(512), nullable=True)
    best_practice = db.Column(db.Text, nullable=True)
    
    # Новые поля для метаданных ошибок
    more_info = db.Column(db.Text, nullable=True)
    issue_severity = db.Column(db.String(50), nullable=True)
    issue_confidence = db.Column(db.String(50), nullable=True)
    issue_cwe_id = db.Column(db.String(50), nullable=True)
    issue_cwe_link = db.Column(db.String(512), nullable=True)

    checker_codes = db.relationship(
        "CheckerCode",
        backref="group_obj",
        lazy="dynamic",
        foreign_keys="CheckerCode.group_key",
        cascade="all, delete-orphan",
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
            "more_info": self.more_info,
            "issue_severity": self.issue_severity,
            "issue_confidence": self.issue_confidence,
            "issue_cwe_id": self.issue_cwe_id,
            "issue_cwe_link": self.issue_cwe_link,
        }

    @classmethod
    def get_or_create(
        cls,
        group_key,
        color="primary",
        name=None,
        translate=None,
        descriptions=None,
        is_hide=False,
        source_url=None,
        best_practice=None,
        more_info=None,
        issue_severity=None,
        issue_confidence=None,
        issue_cwe_id=None,
        issue_cwe_link=None,
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
                more_info=more_info,
                issue_severity=issue_severity,
                issue_confidence=issue_confidence,
                issue_cwe_id=issue_cwe_id,
                issue_cwe_link=issue_cwe_link,
            )
            db.session.add(group)
            db.session.commit()
        return group

    @classmethod
    def union(cls, group_key_list):
        """
        ГРУППИРОВКА: Объединение нескольких групп в одну.
        В качестве нового group_key записывается текущее время в формате Epoch.
        """
        if not group_key_list:
            return None
        uniq_keys = list(dict.fromkeys(group_key_list))
        epoch_group_key = str(int(time.time()))
        source_groups = cls.query.filter(cls.group_key.in_(uniq_keys)).all()
        if not source_groups:
            return None

        main_group = cls.query.filter_by(group_key=epoch_group_key).first()
        if not main_group:
            first_g = source_groups[0]
            main_group = cls(
                group_key=epoch_group_key,
                color=first_g.color,
                name=first_g.name or "Объединенная группа линтера",
                translate=first_g.translate,
                descriptions=first_g.descriptions,
                is_hide=first_g.is_hide,
                source_url=first_g.source_url,
                best_practice=first_g.best_practice,
                more_info=first_g.more_info,
                issue_severity=first_g.issue_severity,
                issue_confidence=first_g.issue_confidence,
                issue_cwe_id=first_g.issue_cwe_id,
                issue_cwe_link=first_g.issue_cwe_link,
            )
            db.session.add(main_group)
            db.session.flush()

        CheckerCode.query.filter(CheckerCode.group_key.in_(uniq_keys)).update(
            {"group_key": epoch_group_key}, synchronize_session=False
        )
        for g in source_groups:
            if g.group_key != epoch_group_key:
                db.session.delete(g)
        db.session.commit()
        return main_group

    @classmethod
    def split(cls, group_key):
        """
        РАЗГРУППИРОВКА: Разъединение ошибок группы.
        Каждому CheckerCode присваивается свой новый сгенерированный UUID.
        """
        obj = cls.query.filter_by(group_key=group_key).first()
        if not obj:
            raise ValueError(f"Group '{group_key}' not found")
        cc_qs = CheckerCode.query.filter_by(group_key=group_key).all()
        result = []
        for cc in cc_qs:
            new_group_uuid = uuid.uuid4().hex
            cc.group_key = new_group_uuid
            new_group = cls.get_or_create(
                group_key=new_group_uuid,
                color=obj.color,
                name=obj.name,
                translate=obj.translate,
                descriptions=obj.descriptions,
                is_hide=obj.is_hide,
                source_url=obj.source_url,
                best_practice=obj.best_practice,
                more_info=obj.more_info,
                issue_severity=obj.issue_severity,
                issue_confidence=obj.issue_confidence,
                issue_cwe_id=obj.issue_cwe_id,
                issue_cwe_link=obj.issue_cwe_link,
            )
            result.append(new_group)
        db.session.delete(obj)
        db.session.commit()
        return result


class CheckerCode(db.Model):
    __tablename__ = "checker_code"
    id = db.Column(db.Integer, primary_key=True)
    checker = db.Column(db.String(32), nullable=False, index=True)
    code = db.Column(db.String(32), nullable=False, index=True)
    group_key = db.Column(
        db.String(32), db.ForeignKey("groups.group_key"), nullable=False, index=True
    )
    # Колонка для хранения "сырых" данных ошибки в формате JSON
    raw_json = db.Column(db.Text, nullable=True)

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

    # Property для автоматического чтения JSON из базы
    @property
    def raw(self):
        if self.raw_json:
            try:
                return json.loads(self.raw_json)
            except json.JSONDecodeError:
                return {}
        return {}

    # Setter для автоматической записи словаря в базу как JSON
    @raw.setter
    def raw(self, value):
        if value:
            self.raw_json = json.dumps(value, ensure_ascii=False)
        else:
            self.raw_json = None

    @classmethod
    def create(
        cls,
        checker,
        code,
        group_key,
        group_color="primary",
        group_name=None,
        group_translate=None,
        group_descriptions=None,
        group_is_hide=False,
        group_source_url=None,
        group_best_practice=None,
        group_more_info=None,
        group_issue_severity=None,
        group_issue_confidence=None,
        group_issue_cwe_id=None,
        group_issue_cwe_link=None,
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
            more_info=group_more_info,
            issue_severity=group_issue_severity,
            issue_confidence=group_issue_confidence,
            issue_cwe_id=group_issue_cwe_id,
            issue_cwe_link=group_issue_cwe_link,
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