import sqlite3

from contextlib import closing, contextmanager
from datetime import datetime
from enum import IntEnum
from flask import Flask, Response, jsonify, abort, request
from functools import partial
from pathlib import Path
from typing import *

_db_file = 'doodle.db'
_schema = Path(__name__).parent / 'schema.sql'

__all__ = ['get_app', 'init_db', 'Role']


class Role(IntEnum):
    INTERVIEWER = 1
    CANDIDATE = 2


class Person(NamedTuple):
    id_: int
    name: str
    role: Role
    times: List[datetime]


@contextmanager
def get_connection(transaction: bool=False) -> Iterator[sqlite3.Connection]:
    '''
    Get a sqlite3 connection object, optionally in a transaction.
    '''
    # Python's DB API transaction model is really weird and counter-intuitive,
    # so just put the connection in auto-commit mode and manage transactions
    # explicitly.
    with closing(sqlite3.connect(_db_file, isolation_level=None)) as connection:
        if transaction:
            connection.execute('BEGIN')
            try:
                yield connection
            except:
                connection.execute('ROLLBACK')
                raise
            else:
                connection.execute('COMMIT')
        else:
            yield connection


def init_db() -> None:
    '''
    Initialise the database from the schema file.
    '''
    with open(_schema) as f:
        script = f.read()
    with get_connection() as c:
        c.executescript(script)


def parse_time(string: str) -> datetime:
    '''
    Convert a string into a datetime.  If it's not valid (i.e., on the hour),
    raise a ValueError.
    '''
    time = datetime.fromisoformat(string)
    if any(t != 0 for t in (time.minute, time.second, time.microsecond)):
        raise ValueError(string)
    return time


def create_person(name: str, role: Role) -> Person:
    '''
    Add a new person to the database with a given name.  Returns the ID of the
    newly added person.
    '''
    with get_connection(transaction=True) as c:
        id_ = c.execute('''
                        INSERT INTO person
                        (name, role)
                        VALUES
                        (:name, :role)
                        ''',
                        {'name': name, 'role': int(role)}) \
               .lastrowid
        return Person(id_, name, role, [])


def get_times(id_: int, role: Role) -> Person:
    '''
    Get the times at which a person is available for an interview.
    '''
    with get_connection() as c:
        rows = c.execute('''
                         SELECT p.name, p.role, t.time
                         FROM person p
                         LEFT JOIN person_time t
                         ON p.id = t.person_id
                         WHERE p.id = :id
                         AND p.role = :role
                         ''',
                         {'id': id_, 'role': int(role)}) \
                .fetchall()
        if rows:
            return Person(id_,
                          rows[0][0],
                          Role(rows[0][1]),
                          [parse_time(r[2]) for r in rows if r[2]])
        else:
            raise KeyError(id_)


def add_times(id_: int, role: Role, times: Iterable[datetime]) -> Person:
    '''
    Add interview times for a given person.  Any times that already exist are
    replaced.  Returns the same as ``get_times``.
    '''
    params = ({'person_id': id_,
               'time': str(time)}
              for time in times)

    with get_connection(transaction=True) as c:
        # Check that he person exists.
        count = c.execute('''
                          SELECT COUNT(*)
                          FROM person p
                          WHERE p.id = :id
                          AND p.role = :role
                          ''',
                          {'id': id_, 'role': int(role)}) \
                 .fetchone()[0]
        if count == 0:
            # No such person.
            raise KeyError(id_)

        c.executemany('''
                      INSERT OR REPLACE INTO person_time
                      (person_id, time)
                      VALUES
                      (:person_id, :time)
                      ''', params)
        rows = c.execute('''
                         SELECT p.name, p.role, t.time
                         FROM person p
                         LEFT JOIN person_time t
                         ON p.id = t.person_id
                         WHERE p.id = :id
                         ''',
                         {'id': id_}) \
                         .fetchall()
        return Person(id_,
                      rows[0][0],
                      Role(rows[0][1]),
                      [parse_time(r[2]) for r in rows if r[2]])


def find_interview_times(ids: Iterable[int]) -> List[datetime]:
    '''
    Get the times at which a list of people are all available.
    '''
    id_params = {f'id{n}': id_ for n, id_ in enumerate(ids)}
    id_list = ', '.join(f':{k}' for k in id_params.keys())

    with get_connection() as c:
        # Group the person/time combinations by time, and count the group sizes.
        # Select only the groups with all the requested people.
        cursor = c.execute(f'''
                           SELECT t.time
                           FROM person p
                           LEFT JOIN person_time t
                           ON p.id = t.person_id
                           WHERE p.id IN ({id_list})
                           GROUP BY t.time
                           HAVING COUNT(p.id) = :count
                           ''',
                           {'count': len(id_params), **id_params})
        return [parse_time(r[0]) for r in cursor if r]


def get_app() -> Flask:
    app = Flask(__name__)

    def person(id_: int, role: Role) -> Response:
        if request.method == 'POST':
            # Add a new person, with no times.
            person = create_person(request.form['name'], role)

        if request.method == 'PUT':
            # Add times to a person.
            try:
                times = request.form.getlist('times', parse_time)
            except ValueError:
                # Couldn't parse the times.
                abort(400, description='Invalid times given.')

            if not times:
                # No times provided.
                abort(400, description='No times given.')

            try:
                person = add_times(id_, role, times)
            except KeyError:
                # The person wasn't found.
                abort(404)

        if request.method == 'GET':
            # Get the times for a person.
            try:
                person = get_times(id_, role)
            except KeyError:
                abort(404)

            if role != person.role:
                abort(404)

        return jsonify(id=person.id_,
                       name=person.name,
                       times=[str(t) for t in person.times])

    @app.route('/candidate/', methods=['POST'])
    @app.route('/candidate/<int:id_>', methods=['GET', 'PUT'])
    def candidate(id_: int=None) -> Response:
        return person(id_, Role.CANDIDATE)

    @app.route('/interviewer/', methods=['POST'])
    @app.route('/interviewer/<int:id_>', methods=['GET', 'PUT'])
    def interviewer(id_: int=None) -> Response:
        return person(id_, Role.INTERVIEWER)

    @app.route('/interview', methods=['GET'])
    def interview_times() -> Response:
        ids = request.args.getlist('id', int)
        if not ids:
            abort(400)
        times = find_interview_times(ids)
        return jsonify(ids=ids,
                       times=[str(t) for t in times])

    return app
