from __future__ import annotations

import enum
import sqlite3

from contextlib import closing, contextmanager
from dataclasses import dataclass
from flask import Flask, Response, jsonify, abort, request
from functools import partial
from typing import *

_url = 'test.db'
_schema = 'schema.sql'

__all__ = ['get_app', 'Slot', 'Role']


@dataclass
class Slot:
    date: datetime.date
    hour: int

    def __post_init__(self):
        if isinstance(self.date, str):
            self.date = datetime.date.fromisoformat(self.date)
        if isinstance(self.hour, str):
            self.hour = int(hour)

        if self.hour < 0 or self.hour > 23:
            raise ValueError(f'invalid hour: {self.hour}')

    @classmethod
    def parse(cls, string: str) -> Slot:
        date, hour = string.split()
        return Slot(date, hour)

    def __str__(self) -> str:
        return f'{self.date} {self.hour}'


class Role(enum.IntEnum):
    INTERVIEWER = 1
    CANDIDATE = 2


@contextmanager
def get_cursor(transaction: bool=False) -> sqlite3.Cursor:
    # Python's DB API transaction model is really weird and counter-intuitive,
    # so just put the connection in auto-commit mode and manage transactions
    # manually.
    with closing(sqlite3.connect(_url, isolation_level=None)) as connection:
        if transaction:
            connection.execute('BEGIN;')
            try:
                yield connection.cursor()
            except:
                connection.execute('ROLLBACK;')
            else:
                connection.execute('COMMIT;')
        else:
            yield connection.cursor()


def init_db() -> None:
    with open(_schema) as f:
        script = f.read()
    with get_cursor() as cursor:
        cursor.executescript(script)


def create_person(name: str, role: Role) -> int:
    with get_cursor(transaction=True) as cursor:
        cursor.execute('''
                       INSERT INTO person
                       (name, role)
                       VALUES
                       (:name, :role);
                       ''',
                       {'name': name, 'role': int(role)})
        return cursor.lastrowid


def get_slots(id_: int) -> Tuple[int, str, Role, List[Slot]]:
    with get_cursor() as cursor:
        cursor.execute('''
                       SELECT p.name, p.role, s.date, s.hour
                       FROM person p
                       LEFT JOIN slot s
                       ON p.id = s.person_id
                       WHERE p.id = :id
                       ''',
                       {'id': id_})
        rows = cursor.fetchall()
        if rows:
            return (id_,
                    rows[0][0],
                    Role(rows[0][1]),
                    [Slot(r[2], r[3]) for r in rows])
        else:
            raise ValueError


def add_slots(id_: int, slots: Iterable[Slot]) -> None:
    params = ({'person_id': id_,
               'date': slot.date,
               'hour': slot.hour}
              for slot in slots)

    with get_cursor() as cursor:
        try:
            cursor.execute('''
                           INSERT INTO slot
                           (person_id, date, hour)
                           VALUES
                           (:person_id, :date, :hour)
                           ''', *params)
        except sqlite3.IntegrityError as e:
            # No such person.
            raise KeyError(id_) from e


def find_interview_slots(ids: Iterable[int]) -> List[Slot]:
    id_params = {f':id{n}': id_ for n, id_ in enumerate(ids)}
    id_list = ', '.join(id_params.keys())

    with get_cursor() as cursor:
        # Get all the slots for any of the specified people.
        cursor.execute(f'''
                       SELECT s.date, s.hour
                       FROM person p
                       WHERE p.id IN ({id_list})
                       JOIN slots s
                       ON p.id = s.person_id
                       GROUP BY s.date, s.hour
                       HAVING COUNT(p.id) = :count
                       ''',
                       {'count': len(ids), **id_params})
        return [Slot(r[3], r[4]) for r in rows]


def get_app() -> Flask:
    init_db()

    app = Flask(__name__)

    def new_person(role: Role) -> Response:
        name = request.form['name']
        id_ = create_person(name, role)
        return jsonify(id=id_)
    app.route('/candidate/', endpoint='new_candidate', methods=['POST']) \
             (partial(new_person, Role.CANDIDATE))
    app.route('/interviewer/', endpoint='new_interviewer', methods=['POST']) \
             (partial(new_person, Role.INTERVIEWER))

    def slots(role: Role, id_: int) -> Response:
        if request.method == 'PUT':
            slots = request.form.getlist('slots')
            if not slots:
                abort(400)

            try:
                add_slots(id_, map(Slot.parse, slots))
            except ValueError:
                abort(404)

            return jsonify()

        if request.method == 'GET':
            try:
                id_, name, role_, slots = get_slots(id_)
            except ValueError:
                abort(404)

            if role != role_:
                abort(404)

            return jsonify(id=id_,
                           name=name,
                           slots=[str(s) for s in slots])
    app.route('/candidate/<int:id_>', endpoint='candidate_slots', methods=['GET', 'PUT']) \
             (partial(slots, Role.CANDIDATE))
    app.route('/interviewer/<int:id_>', endpoint='interviewer_slots', methods=['GET', 'PUT']) \
             (partial(slots, Role.INTERVIEWER))

    @app.route('/interview', methods=['GET'])
    def common_slots() -> Response:
        ids = request.args.getlist('id', int)
        slots = find_interview_slots(ids)
        return jsonify(ids=ids,
                       slots=[str(s) for s in slots])

    return app
