CREATE TABLE IF NOT EXISTS contacts_encrypted_scan (
    id BIGINT PRIMARY KEY,
    surname_ciphertext BYTEA NOT NULL,
    email_ciphertext BYTEA NOT NULL
);