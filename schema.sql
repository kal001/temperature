CREATE TABLE sensors
(
    name TEXT NOT NULL,
    id TEXT NOT NULL,
    baudrate INTEGER,
    porta TEXT NOT NULL
);
CREATE TABLE temps
(
    timestamp TEXT,
    temp REAL,
    ID TEXT
);
