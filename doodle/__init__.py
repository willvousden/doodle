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
def get_connection(transaction: bool=False) -> Iterator[sqlite3.Connection]:
    '''
    Get a sqlite3 connection object, optionally in a transaction.
    '''
    # Python's DB API transaction model is really weird and counter-intuitive,
    # so just put the connection in auto-commit mode and manage transactions
    # explicitly.
    with closing(sqlite3.connect(_url, isolation_level=None)) as connection:
        if transaction:
            connection.execute('BEGIN;')
            try:
                yield connection
            except:
                connection.execute('ROLLBACK;')
                raise
            else:
                connection.execute('COMMIT;')
        else:
            yield connection


def init_db() -> None:
    '''
    Initialise the database from the schema file.
    '''
    with open(_schema) as f:
        script = f.read()
    with get_connection() as connection:
        connection.executescript(script)


def validate_time(time: datetime) -> bool:
    '''
    Determine whether a time is a valid interview time; that is, whether it's on
    the hour.
    '''
    return all(t == 0 for t in (time.minute, time.second, time.microsecond))


def create_person(name: str, role: Role) -> int:
    with get_connection(transaction=True) as connection:
        return connection.execute('''
                                  INSERT INTO person
                                  (name, role)
                                  VALUES
                                  (:name, :role);
                                  ''',
                                  {'name': name, 'role': int(role)}) \
                         .lastrowid


def get_times(id_: int) -> Tuple[int, str, Role, List[datetime]]:
    with get_connection() as connection:
        rows = connection.execute('''
                                  SELECT p.name, p.role, t.time
                                  FROM person p
                                  LEFT JOIN person_time t
                                  ON p.id = t.person_id
                                  WHERE p.id = :id
                                  ''',
                                  {'id': id_}) \
                         .fetchall()
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

    with get_connection(transaction=True) as connection:
        count = connection.execute('''
                                   SELECT COUNT(*)
                                   FROM person p
                                   WHERE p.id = :id
                                   ''', {'id': id_}) \
                          .fetchone()[0]
        if count == 0:
            # No such person.
            raise KeyError(id_)

        connection.executemany('''
                               INSERT OR REPLACE INTO person_time
                               (person_id, time)
                               VALUES
                               (:person_id, :time)
                               ''', params)


def find_interview_times(ids: Iterable[int]) -> List[datetime]:
    '''
    Get the times at which a list of people are all available.
    '''
    id_params = {f'id{n}': id_ for n, id_ in enumerate(ids)}
    id_list = ', '.join(f':{k}' for k in id_params.keys())

    with get_connection() as connection:
        # Get all the times for any of the specified people.
        cursor = connection.execute(f'''
                                    SELECT t.time
                                    FROM person p
                                    JOIN person_time t
                                    ON p.id = t.person_id
                                    WHERE p.id IN ({id_list})
                                    GROUP BY t.time
                                    HAVING COUNT(p.id) = :count
                                    ''',
                                    {'count': len(id_params), **id_params})
        return [datetime.fromisoformat(r[0]) for r in cursor if r]


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
        if not ids:
            abort(400)
        times = find_interview_times(ids)
        return jsonify(ids=ids,
                       times=[str(t) for t in times])

    return app
