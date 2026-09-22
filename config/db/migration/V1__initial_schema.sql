-- Initial schema.
--
-- Two notes on choices that differ from the upstream FastAPI template:
--
-- 1. Primary keys are CHAR(36) rather than BINARY(16). MySQL has no native
--    UUID type. BINARY(16) is more compact and indexes marginally better;
--    CHAR(36) is legible in a `SELECT`, which matters more in a template that
--    exists to be read. See PLAN.md section 7.1.
--
-- 2. The item -> user cascade is declared here, in the database, rather than
--    in the mapping layer. Micronaut Data JDBC does not cascade deletes, and
--    a foreign key that says what it means is the more honest implementation.

CREATE TABLE users (
    id                CHAR(36)     NOT NULL,
    email             VARCHAR(255) NOT NULL,
    hashed_password   VARCHAR(255) NOT NULL,
    full_name         VARCHAR(255) NULL,
    is_active         BOOLEAN      NOT NULL DEFAULT TRUE,
    is_superuser      BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at        DATETIME(6)  NOT NULL,
    CONSTRAINT pk_users PRIMARY KEY (id),
    CONSTRAINT uq_users_email UNIQUE (email)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE items (
    id           CHAR(36)     NOT NULL,
    title        VARCHAR(255) NOT NULL,
    description  VARCHAR(255) NULL,
    owner_id     CHAR(36)     NOT NULL,
    created_at   DATETIME(6)  NOT NULL,
    CONSTRAINT pk_items PRIMARY KEY (id),
    CONSTRAINT fk_items_owner FOREIGN KEY (owner_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE INDEX idx_items_owner_id ON items (owner_id);
