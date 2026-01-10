from datetime import datetime

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from tiebameow.models.dto import BaseUserDTO, CommentDTO, PostDTO, ThreadDTO
from tiebameow.models.orm import Comment, MixinBase, Post, ReviewRules, Thread, User
from tiebameow.schemas.rules import Action, ActionType, Condition, FieldType, OperatorType, ReviewRule, TargetType


class TestORMMethods:
    def test_mixin_to_dict(self):
        # Create a dummy model using MixinBase
        # We use __abstract__ = True to avoid SQLAlchemy mapper registration issues
        class Dummy(MixinBase):
            __tablename__ = "dummy"

            id: Mapped[int] = mapped_column(Integer, primary_key=True)
            name: Mapped[str] = mapped_column(String)

        d = Dummy(id=1, name="foo")

        res = d.to_dict()
        assert res == {"id": 1, "name": "foo"}

    def test_user_from_dto(self):
        dto = BaseUserDTO(user_id=123, portrait="portrait", user_name="name", nick_name_new="nick")

        user = User.from_dto(dto)
        assert user.user_id == 123
        assert user.portrait == "portrait"
        assert user.user_name == "name"
        assert user.nick_name == "nick"

    def test_thread_from_dto(self):
        dto = ThreadDTO.from_incomplete_data({})
        dto.tid = 100
        dto.create_time = datetime.now()
        dto.title = "t"
        dto.text = "txt"
        dto.contents = []
        dto.last_time = datetime.now()
        dto.reply_num = 5
        dto.author.level = 10
        dto.fid = 50
        dto.author_id = 99

        t = Thread.from_dto(dto)
        assert t.tid == 100
        assert t.author_level == 10
        assert t.fid == 50

    def test_post_from_dto(self):
        dto = PostDTO.from_incomplete_data({})
        dto.pid = 200
        dto.create_time = datetime.now()
        dto.text = "p"
        dto.contents = []
        dto.floor = 2
        dto.reply_num = 1
        dto.author.level = 5
        dto.tid = 100
        dto.fid = 50
        dto.author_id = 99

        p = Post.from_dto(dto)
        assert p.pid == 200
        assert p.floor == 2
        assert p.tid == 100

    def test_comment_from_dto(self):
        dto = CommentDTO.from_incomplete_data({})
        dto.cid = 300
        dto.create_time = datetime.now()
        dto.text = "c"
        dto.contents = []
        dto.author.level = 3
        dto.reply_to_id = 88
        dto.pid = 200
        dto.tid = 100
        dto.fid = 50
        dto.author_id = 99

        c = Comment.from_dto(dto)
        assert c.cid == 300
        assert c.reply_to_id == 88

    def test_review_rules_conversion(self):
        trigger = Condition(field=FieldType.TEXT, operator=OperatorType.EQ, value="x")
        act = Action(type=ActionType.DELETE)

        rule_data = ReviewRule(
            id=1,
            fid=10,
            forum_rule_id=2,
            name="test",
            trigger=trigger,
            actions=[act],
            target_type=TargetType.POST,
            enabled=True,
            priority=1,
        )

        orm_obj = ReviewRules.from_rule_data(rule_data)
        assert orm_obj.fid == 10
        assert orm_obj.name == "test"

        orm_obj.id = 1
        orm_obj.created_at = datetime.now()
        orm_obj.updated_at = datetime.now()

        out_data = orm_obj.to_rule_data()
        assert out_data.fid == 10
        assert out_data.name == "test"
        assert out_data.trigger == trigger
