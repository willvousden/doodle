CREATE TABLE candidate (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);

CREATE TABLE interviewer (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);

CREATE TABLE candidate_slot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER,
    date INTEGER NOT NULL,
    hour INTEGER NOT NULL,
    FOREIGN KEY (candidate_id) REFERENCES candidate (id)
);

CREATE TABLE interviewer_slot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interviewer_id INTEGER,
    date INTEGER NOT NULL,
    hour INTEGER NOT NULL,
    FOREIGN KEY (interviewer_id) REFERENCES interviewer (id)
);
