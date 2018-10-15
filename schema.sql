CREATE TABLE IF NOT EXISTS person (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role INTEGER NOT NULL,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS person_time (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER,
    time TEXT NOT NULL,
    FOREIGN KEY (person_id) REFERENCES person (id),
    UNIQUE (person_id, time)
);
