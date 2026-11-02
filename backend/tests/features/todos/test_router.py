import pytest

from app.features.todos.schemas import TodoCreate


def test_list_returns_tasks_from_repository(client, repository_mock, todo):
    repository_mock.list.return_value = [todo]
    response = client.get("/api/todos")
    assert response.status_code == 200
    assert response.json() == [todo.model_dump(mode="json")]
    repository_mock.list.assert_called_once_with()


def test_create_trims_input_and_returns_created_task(client, repository_mock, todo):
    repository_mock.create.return_value = todo
    response = client.post("/api/todos", json={"title": "  Plan the sprint  ", "priority": "high"})
    assert response.status_code == 201
    assert response.json() == todo.model_dump(mode="json")
    repository_mock.create.assert_called_once_with(
        TodoCreate(title="Plan the sprint", priority="high")
    )


@pytest.mark.parametrize("payload", [
    {"title": "   "},
    {"title": "x" * 121},
    {"title": "Task", "priority": "urgent"},
    {"title": "Task", "due_date": "2026-02-30"},
])
def test_invalid_create_never_calls_repository(client, repository_mock, payload):
    assert client.post("/api/todos", json=payload).status_code == 422
    repository_mock.create.assert_not_called()


def test_get_returns_a_single_task(client, repository_mock, todo):
    repository_mock.get.return_value = todo
    response = client.get("/api/todos/7")
    assert response.status_code == 200
    assert response.json() == todo.model_dump(mode="json")
    repository_mock.get.assert_called_once_with(7)


@pytest.mark.parametrize("method, extra", [
    ("get", {}),
    ("patch", {"json": {"completed": True}}),
    ("delete", {}),
])
def test_missing_task_returns_404(client, repository_mock, method, extra):
    repository_mock.get.return_value = None
    repository_mock.update.return_value = None
    repository_mock.delete.return_value = False
    response = client.request(method.upper(), "/api/todos/404", **extra)
    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found."}


@pytest.mark.parametrize("todo_id", ["0", "-1", "abc"])
def test_invalid_task_id_is_rejected_before_reaching_repository(client, repository_mock, todo_id):
    assert client.get(f"/api/todos/{todo_id}").status_code == 422
    assert client.patch(f"/api/todos/{todo_id}", json={"completed": True}).status_code == 422
    assert client.delete(f"/api/todos/{todo_id}").status_code == 422
    assert repository_mock.mock_calls == []


def test_update_passes_only_provided_fields_and_returns_saved_task(client, repository_mock, todo):
    saved = todo.model_copy(update={"completed": True})
    repository_mock.update.return_value = saved
    response = client.patch("/api/todos/7", json={"completed": True, "due_date": None})
    assert response.status_code == 200
    assert response.json() == saved.model_dump(mode="json")
    todo_id, patch = repository_mock.update.call_args.args
    assert todo_id == 7
    assert patch.model_dump(exclude_unset=True) == {"completed": True, "due_date": None}


@pytest.mark.parametrize("payload", [{}, {"title": None}, {"completed": "yes"}, {"unknown": 1}])
def test_invalid_patch_never_calls_repository(client, repository_mock, payload):
    assert client.patch("/api/todos/7", json=payload).status_code == 422
    repository_mock.update.assert_not_called()


def test_delete_returns_empty_204(client, repository_mock):
    repository_mock.delete.return_value = True
    response = client.delete("/api/todos/7")
    assert response.status_code == 204
    assert response.content == b""
    repository_mock.delete.assert_called_once_with(7)
