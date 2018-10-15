from __future__ import annotations

import enum
import sqlite3

from contextlib import closing, contextmanager
from datetime import datetime
from flask import Flask, Response, jsonify, abort, request
from functools import partial
from typing import *

_url = 'test.db'
_schema = 'schema.sql'

__all__ = ['get_app', 'Role']


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
                raise
            else:
                connection.execute('COMMIT;')
        else:
            yield connection.cursor()


def init_db() -> None:
    with open(_schema) as f:
        script = f.read()
    with get_cursor() as cursor:
        cursor.executescript(script)


def validate_time(time: datetime) -> bool:
    return all(t == 0 for t in (time.minute, time.second, time.microsecond))


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


def get_times(id_: int) -> Tuple[int, str, Role, List[datetime]]:
    with get_cursor() as cursor:
        cursor.execute('''
                       SELECT p.name, p.role, t.time
                       FROM person p
                       LEFT JOIN person_time t
                       ON p.id = t.person_id
                       WHERE p.id = :id
                       ''',
                       {'id': id_})
        rows = cursor.fetchall()
        if rows:
            return (id_,
                    rows[0][0],
                    Role(rows[0][1]),
                    [datetime.fromisoformat(r[2]) for r in rows if r])
        else:
            raise KeyError(id_)


def add_times(id_: int, times: Iterable[datetime]) -> None:
    params = ({'person_id': id_,
               'time': str(time)}
              for time in times)

    with get_cursor(transaction=True) as cursor:
        cursor.execute('SELECT COUNT(*) FROM person p WHERE p.id = :id',
                       {'id': id_})
        if cursor.fetchone()[0] == 0:
            # No such person.
            raise KeyError(id_)

        cursor.executemany('''
                           INSERT OR REPLACE INTO person_time
                           (person_id, time)
                           VALUES
                           (:person_id, :time)
                           ''', params)


def find_interview_times(ids: Iterable[int]) -> List[datetime]:
    id_params = {f':id{n}': id_ for n, id_ in enumerate(ids)}
    id_list = ', '.join(id_params.keys())

    with get_cursor() as cursor:
        # Get all the times for any of the specified people.
        cursor.execute(f'''
                       SELECT t.time
                       FROM person p
                       WHERE p.id IN ({id_list})
                       JOIN person_time t
                       ON p.id = t.person_id
                       GROUP BY t.time
                       HAVING COUNT(p.id) = :count
                       ''',
                       {'count': len(ids), **id_params})
        return [datetime.fromisoformat(r[2]) for r in rows if r]


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

    def times(role: Role, id_: int) -> Response:
        if request.method == 'PUT':
            invalid_times = False
            try:
                times = [datetime.fromisoformat(t)
                         for t in request.form.getlist('times')]
            except ValueError:
                # Couldn't parse the times.
                invalid_times = True

            # Times must be on the hour.
            invalid_times |= not all(map(validate_time, times))
            if invalid_times:
                abort(400, description='Invalid times given.')

            if not times:
                # No times provided.
                abort(400, description='No times given.')

            try:
                add_times(id_, times)
            except KeyError:
                # The person wasn't found.
                abort(404)

            return jsonify()

        if request.method == 'GET':
            try:
                id_, name, role_, times = get_times(id_)
            except KeyError:
                abort(404)

            if role != role_:
                abort(404)

            return jsonify(id=id_,
                           name=name,
                           times=[str(t) for t in times])
    app.route('/candidate/<int:id_>', endpoint='candidate_times', methods=['GET', 'PUT']) \
             (partial(times, Role.CANDIDATE))
    app.route('/interviewer/<int:id_>', endpoint='interviewer_times', methods=['GET', 'PUT']) \
             (partial(times, Role.INTERVIEWER))

    @app.route('/interview', methods=['GET'])
    def common_times() -> Response:
        ids = request.args.getlist('id', int)
        times = find_interview_times(ids)
        return jsonify(ids=ids,
                       times=[str(t) for t in times])

    return app
