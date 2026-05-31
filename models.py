from extensions import db
from sqlalchemy import func, tuple_


class Group(db.Model):
    __tablename__ = "groups"
    
    id = db.Column(db.Integer, primary_key=True)
    group_key = db.Column(db.String(64), unique=True, nullable=False, index=True)
    color = db.Column(db.String(32), nullable=False, default="#cccccc")
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
        """Получить существующую группу или создать новую."""
        obj = cls.query.filter_by(group_key=group_key).first()
        if obj is None:
            obj = cls(group_key=group_key, **defaults)
            db.session.add(obj)
        return obj
    
    @classmethod
    def get_color(cls, group_key, default="#cccccc"):
        """Быстро получить цвет группы по ключу."""
        obj = cls.query.filter_by(group_key=group_key).first()
        return obj.color if obj else default


class CheckerCode(db.Model):
    __tablename__ = "checker_code"
    
    id = db.Column(db.Integer, primary_key=True)
    checker = db.Column(db.String(64), nullable=False, index=True)
    code = db.Column(db.String(32), nullable=False, index=True)
    group_key = db.Column(db.String(64), nullable=False, index=True)
    
    __table_args__ = (
        db.UniqueConstraint("checker", "code", name="uq_checker_code"),
    )
    
    def __repr__(self):
        return f"<CheckerCode {self.id}: {self.checker}:{self.code} → {self.group_key}>"
    
    @property
    def color(self):
        """Получить цвет из связанной группы."""
        return Group.get_color(self.group_key)
    
    @property
    def group_params(self):
        """Получить все параметры группы как словарь."""
        group = Group.query.filter_by(group_key=self.group_key).first()
        return group.to_dict() if group else {}
    
    def get_param(self, name, default=None):
        """Получить конкретный параметр группы."""
        group = Group.query.filter_by(group_key=self.group_key).first()
        return getattr(group, name, default) if group else default
    
    def to_dict(self):
        return {
            "id": self.id,
            "checker": self.checker,
            "code": self.code,
            "group_key": self.group_key,
            "color": self.color,
            "params": self.group_params,
        }
    
    # === Фабричные методы ===
    
    @classmethod
    def get_or_create(cls, checker, code, group_key=None):
        """Получить или создать запись. Авто-генерация group_key при создании."""
        obj = cls.query.filter_by(checker=checker, code=code).first()
        if obj is None:
            if group_key is None:
                group_key = cls._generate_default_group_key(checker, code)
            obj = cls(checker=checker, code=code, group_key=group_key)
            db.session.add(obj)
        return obj
    
    @staticmethod
    def _generate_default_group_key(checker, code):
        """Генерация уникального ключа по умолчанию."""
        return f"{checker.lower()}_{code.lower()}"
    
    # === Методы группировки ===
    
    def group_with(self, other):
        """
        Объединить с другой записью в одну группу.
        :param other: объект CheckerCode или кортеж (checker, code)
        :return: self
        """
        if isinstance(other, (tuple, list)):
            other_checker, other_code = other
            other_obj = CheckerCode.query.filter_by(
                checker=other_checker, code=other_code
            ).first()
            if other_obj is None:
                raise ValueError(f"CheckerCode({other_checker}, {other_code}) not found")
            target_key = other_obj.group_key
        elif isinstance(other, CheckerCode):
            target_key = other.group_key
        else:
            raise TypeError("Expected CheckerCode or (checker, code) tuple")
        
        self.group_key = target_key
        return self
    
    def group_by_key(self, group_key):
        """Назначить запись в группу по произвольному ключу."""
        self.group_key = group_key
        return self
    
    def ungroup(self):
        """
        Разгруппировать: назначить уникальный group_key.
        Запись получит независимые параметры.
        """
        self.group_key = self._generate_default_group_key(self.checker, self.code) + f"_{self.id}"
        return self
    
    @classmethod
    def group_multiple(cls, items, group_key=None):
        """
        Объединить несколько записей в одну группу.
        :param items: список CheckerCode объектов или (checker, code) кортежей
        :param group_key: ключ целевой группы (если None — берётся из первой записи)
        """
        if not items:
            return []
        
        # Нормализация: загружаем объекты если переданы кортежи
        objects = []
        for item in items:
            if isinstance(item, (tuple, list)):
                obj = cls.query.filter_by(checker=item[0], code=item[1]).first()
            elif isinstance(item, CheckerCode):
                obj = item
            else:
                continue
            if obj:
                objects.append(obj)
        
        if not objects:
            return []
        
        if group_key is None:
            group_key = objects[0].group_key
        
        for obj in objects:
            obj.group_key = group_key
        
        return objects
    
    @classmethod
    def get_by_group_key(cls, group_key):
        """Получить все записи, принадлежащие группе."""
        return cls.query.filter_by(group_key=group_key).all()
    
    @classmethod
    def get_grouped_summary(cls):
        """
        Сводка по группам: какие группы существуют и сколько записей в каждой.
        Возвращает: [(group_key, count, color, name), ...]
        """
        results = db.session.query(
            cls.group_key,
            func.count(cls.id).label('count')
        ).group_by(cls.group_key).all()
        
        summary = []
        for group_key, count in results:
            group = Group.query.filter_by(group_key=group_key).first()
            color = group.color if group else "#cccccc"
            name = group.name if group else None
            summary.append((group_key, count, color, name))
        
        return summary
    
    @classmethod
    def bulk_get_colors(cls, checker_code_pairs):
        """
        Получить цвета для множества пар (checker, code) ОДНИМ запросом.
        :param checker_code_pairs: список кортежей [(checker, code), ...]
        :return: dict {(checker, code): color}
        """
        if not checker_code_pairs:
            return {}
        
        # Один запрос: получаем все нужные CheckerCode записи
        stmt = db.select(cls).filter(
            tuple_(cls.checker, cls.code).in_(checker_code_pairs)
        )
        records = db.session.scalars(stmt).all()
        
        # Кэшируем цвета групп чтобы избежать N+1
        group_keys = {r.group_key for r in records}
        groups_cache = {
            g.group_key: g.color 
            for g in Group.query.filter(Group.group_key.in_(group_keys)).all()
        }
        
        return {
            (r.checker, r.code): groups_cache.get(r.group_key, "#cccccc")
            for r in records
        }