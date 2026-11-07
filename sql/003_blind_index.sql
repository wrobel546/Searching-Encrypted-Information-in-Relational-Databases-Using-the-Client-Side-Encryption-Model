CREATE TABLE IF NOT EXISTS contacts_blind_index (
    id BIGINT PRIMARY KEY,
    surname_ciphertext BYTEA NOT NULL,
    email_ciphertext BYTEA NOT NULL,
    surname_token BYTEA NOT NULL
        CHECK (octet_length(surname_token) = 32)
);

CREATE INDEX IF NOT EXISTS idx_contacts_blind_index_surname_token
    ON contacts_blind_index USING btree (surname_token);