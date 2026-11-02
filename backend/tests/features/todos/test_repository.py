from datetime import datetime, timezone
from unittest.mock import Mock, call

from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.features.todos.models import TodoRecord
from app.features.todos.repository import TodoRepository
from app.features.todos.schemas import TodoCreate, TodoUpdate


def test_list_maps_models_and_orders_tasks_newest_first(model_factory, todo_values, todo):
    session = Mock(spec=Session)
    session.scalars.return_value = [model_factory(todo_values)]
    assert TodoRepository(session).list() == [todo]
    statement = session.scalars.call_args.args[0]
    expected = select(TodoRecord).order_by(TodoRecord.created_at.desc(), TodoRecord.id.desc())
    assert statement.compare(expected)
    compiled = str(statement.compile(dialect=postgresql.dialect()))
    assert "ORDER BY todos.created_at DESC, todos.id DESC" in compiled


def test_get_returns_none_for_missing_task():
    session = Mock(spec=Session)
    session.get.return_value = None
    assert TodoRepository(session).get(404) is None
    session.get.assert_called_once_with(TodoRecord, 404)


def test_get_maps_an_existing_task(model_factory, todo_values, todo):
    session = Mock(spec=Session)
    session.get.return_value = model_factory(todo_values)
    assert TodoRepository(session).get(7) == todo


def test_create_persists_payload_with_utc_timestamps_and_returns_refreshed_task():
    session = Mock(spec=Session)
    session.refresh.side_effect = lambda record: setattr(record, "id", 11)
    before = datetime.now(timezone.utc)
    created = TodoRepository(session).create(TodoCreate(title="Write tests", priority="low"))
    after = datetime.now(timezone.utc)

    record = session.add.call_args.args[0]
    assert isinstance(record, TodoRecord)
    assert session.method_calls == [call.add(record), call.commit(), call.refresh(record)]
    assert created.id == 11
    assert created.title == "Write tests"
    assert created.priority == "low"
    assert created.completed is False
    assert before <= created.created_at <= after
    assert created.created_at.tzinfo is timezone.utc
    assert created.updated_at == created.created_at


def test_update_applies_only_fields_set_in_the_patch(model_factory, todo_values):
    record = model_factory(todo_values)
    session = Mock(spec=Session)
    session.get.return_value = record
    updated = TodoRepository(session).update(7, TodoUpdate(completed=True, due_date=None))
    assert updated.completed is True
    assert updated.title == todo_values["title"]
    assert updated.priority == "high"
    assert updated.due_date is None
    assert updated.created_at == todo_values["created_at"]
    assert updated.updated_at > todo_values["updated_at"]
    session.get.assert_called_once_with(TodoRecord, 7)
    session.commit.assert_called_once_with()
    session.refresh.assert_called_once_with(record)


def test_update_returns_none_without_committing_for_missing_task():
    session = Mock(spec=Session)
    session.get.return_value = None
    assert TodoRepository(session).update(404, TodoUpdate(title="New")) is None
    session.commit.assert_not_called()


def test_delete_removes_an_existing_task(model_factory, todo_values):
    record = model_factory(todo_values)
    session = Mock(spec=Session)
    session.get.return_value = record
    assert TodoRepository(session).delete(7) is True
    assert session.method_calls == [call.get(TodoRecord, 7), call.delete(record), call.commit()]


def test_delete_returns_false_without_committing_for_missing_task():
    session = Mock(spec=Session)
    session.get.return_value = None
    assert TodoRepository(session).delete(404) is False
    session.delete.assert_not_called()
    session.commit.assert_not_called()
