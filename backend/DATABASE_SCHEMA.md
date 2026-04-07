# Database Schema — Brainiac5

SQLite database located at `data/knowledge.db` (path configured via `NAME_DB` env var).

Initialized by `data_handler.init_database()` on application startup.

---

## Tables

### `users`

Stores registered users. Authentication uses TOTP (Google Authenticator); the OTP secret is stored in `hashed_password`.

| Column            | Type    | Constraints               | Description                          |
|-------------------|---------|---------------------------|--------------------------------------|
| `id`              | INTEGER | PRIMARY KEY AUTOINCREMENT | Surrogate key                        |
| `username`        | TEXT    | UNIQUE NOT NULL            | Derived from email (part before `@`) |
| `email`           | TEXT    | UNIQUE NOT NULL            | Login identifier; used as JWT `sub`  |
| `hashed_password` | TEXT    | NOT NULL                  | TOTP secret (base32, via pyotp)      |

> **Note:** Despite the column name, `hashed_password` stores a raw TOTP secret, not a hashed password.

---

### `tags`

A flat list of labels that can be attached to ideas.

| Column | Type | Constraints | Description      |
|--------|------|-------------|------------------|
| `name` | TEXT | PRIMARY KEY | Unique tag label |

---

### `books`

A collection that groups related ideas. Each idea belongs to exactly one book. A book can have multiple authors via the `book_authors` junction table.

| Column  | Type    | Constraints               | Description         |
|---------|---------|---------------------------|---------------------|
| `id`    | INTEGER | PRIMARY KEY AUTOINCREMENT | Surrogate key       |
| `title` | TEXT    | NOT NULL                  | Title of the book   |

---

### `ideas`

The core content entities of the application. Each idea belongs to a single book and is owned by one user.

| Column     | Type    | Constraints                        | Description                       |
|------------|---------|-------------------------------------|-----------------------------------|
| `id`       | INTEGER | PRIMARY KEY AUTOINCREMENT          | Surrogate key                     |
| `title`    | TEXT    | NOT NULL                           | Short name of the idea            |
| `content`  | TEXT    | NOT NULL                           | Full body text of the idea        |
| `owner_id` | INTEGER | NOT NULL, FOREIGN KEY → `users.id` | User who created the idea         |
| `book_id`  | INTEGER | NOT NULL, FOREIGN KEY → `books.id` | Book this idea belongs to         |

> Ideas are also indexed in ChromaDB (vector store) via `chroma_client.py` using the `all-distilroberta-v1` sentence transformer model. The SQLite record and ChromaDB embedding are kept in sync by `data_handler` (insert/update/delete operations touch both stores).

---

### `relations`

Many-to-many join table between `ideas` and `tags`.

| Column     | Type    | Constraints                              | Description       |
|------------|---------|------------------------------------------|-------------------|
| `idea_id`  | INTEGER | PRIMARY KEY (composite), FK → `ideas.id` | Reference to idea |
| `tag_name` | TEXT    | PRIMARY KEY (composite), FK → `tags.name`| Reference to tag  |

The composite `(idea_id, tag_name)` pair is the primary key, preventing duplicate associations.

---

### `book_authors`

Many-to-many join table between `books` and `users`. Records which users are authors/participants of a book.

| Column    | Type    | Constraints                              | Description        |
|-----------|---------|------------------------------------------|--------------------|
| `book_id` | INTEGER | PRIMARY KEY (composite), FK → `books.id` | Reference to book  |
| `user_id` | INTEGER | PRIMARY KEY (composite), FK → `users.id` | Reference to user  |

The composite `(book_id, user_id)` pair is the primary key, preventing duplicate authorship entries.

---

## Entity-Relationship Diagram

```
users
  id ──────────────────┬────────────────────────────┐
  username             │                            │
  email                │                            │
  hashed_password      │ owner_id (FK)              │ user_id (FK)
                       │                            │
ideas                  │              book_authors  │
  id ◄──────────────── owner_id       book_id ──────┤
  title                               user_id ──────┘
  content
  book_id ─── FK → books
                          books
                            id ◄─── book_id (book_authors)
                            title

        ┌──────────────────────┐
        │                      │
relations (junction table)     │
  idea_id  ─── FK → ideas.id   │
  tag_name ─── FK → tags.name  │
                                │
                               tags
                                 name (PK)
```

---

## Constraints & Integrity

- **No ON DELETE CASCADE** is defined. Deleting a `user`, `book`, or `tag` while related rows exist in `ideas`, `book_authors`, or `relations` will violate foreign key constraints if FK enforcement is enabled at connection time (SQLite requires `PRAGMA foreign_keys = ON`).
- Duplicate tags and duplicate relations are silently swallowed at the application layer.
- `book_id` is required (`NOT NULL`) when creating an idea; the API returns HTTP 400 if omitted.

---

## ChromaDB (vector store)

Not part of the SQLite schema, but logically coupled:

- **Collection:** one collection per `ChromaClient` instance (path configured via `CHROMA_DB` env var).
- **Model:** `all-distilroberta-v1` (Sentence Transformers).
- **Document key:** idea `title`.
- **Payload stored:** `title` + `content`.
- Operations `insert_idea`, `update_idea`, `remove_idea` mirror every SQLite write.

---

## Key Queries

| Purpose                           | Tables touched                              |
|-----------------------------------|---------------------------------------------|
| All ideas with tags               | `ideas` LEFT JOIN `relations`               |
| Ideas owned by a user             | `ideas` JOIN `relations` JOIN `users`       |
| Ideas filtered by tags            | `ideas` JOIN `relations` JOIN `tags`        |
| Tags for a given idea             | `relations` WHERE `idea_id = ?`             |
| User lookup for TOTP verify       | `users` WHERE `email = ?`                   |
| Owner lookup when adding idea     | `users` WHERE `email = ?`                   |
| Authors of a book                 | `users` JOIN `book_authors` WHERE `book_id` |
