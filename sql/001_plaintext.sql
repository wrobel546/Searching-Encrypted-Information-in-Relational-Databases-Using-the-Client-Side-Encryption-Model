CREATE TABLE IF NOT EXISTS contacts_plaintext (
    id BIGINT PRIMARY KEY,
    surname TEXT NOT NULL,
    surname_normalized TEXT COLLATE "C" NOT NULL,
    email TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_contacts_plaintext_surname_normalized
    ON contacts_plaintext USING btree (surname_normalized);