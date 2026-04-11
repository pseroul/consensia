# Database Schema — Consensia

SQLite database located at `data/knowledge.db` (path configured via `NAME_DB` env var).

Initialized by `data_handler.init_database()` on application startup.

---

## Tables

### `users`

Stores registered users. Authentication uses TOTP (Google Authenticator); the OTP secret is stored in `hashed_password`.

| Column            | Type    | Constraints                | Description                          |
|-------------------|---------|----------------------------|--------------------------------------|
| `id`              | INTEGER | PRIMARY KEY AUTOINCREMENT  | Surrogate key                        |
| `username`        | TEXT    | UNIQUE NOT NULL             | Derived from email (part before `@`) |
| `email`           | TEXT    | UNIQUE NOT NULL             | Login identifier; used as JWT `sub`  |
| `hashed_password` | TEXT    | NOT NULL                   | TOTP secret (base32, via pyotp)      |
| `is_admin`        | INTEGER | NOT NULL DEFAULT 0         | 1 = admin, 0 = regular user (migration-added) |

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

| Column  | Type    | Constraints               | Description       |
|---------|---------|---------------------------|-------------------|
| `id`    | INTEGER | PRIMARY KEY AUTOINCREMENT | Surrogate key     |
| `title` | TEXT    | NOT NULL                  | Title of the book |

---

### `ideas`

The core content entities of the application. Each idea belongs to a single book and is owned by one user.

| Column     | Type    | Constraints                         | Description                   |
|------------|---------|-------------------------------------|-------------------------------|
| `id`       | INTEGER | PRIMARY KEY AUTOINCREMENT           | Surrogate key                 |
| `title`    | TEXT    | NOT NULL                            | Short name of the idea        |
| `content`  | TEXT    | NOT NULL                            | Full body text of the idea    |
| `owner_id` | INTEGER | NOT NULL, FOREIGN KEY → `users.id`  | User who created the idea     |
| `book_id`  | INTEGER | NOT NULL, FOREIGN KEY → `books.id`  | Book this idea belongs to     |

> Ideas are also indexed in ChromaDB via `chroma_client.py` using the `all-distilroberta-v1` sentence transformer model. The SQLite record and ChromaDB embedding are kept in sync by `data_handler` (insert/update/delete touch both stores).

---

### `relations`

Many-to-many join table between `ideas` and `tags`.

| Column     | Type    | Constraints                               | Description       |
|------------|---------|-------------------------------------------|-------------------|
| `idea_id`  | INTEGER | PRIMARY KEY (composite), FK → `ideas.id`  | Reference to idea |
| `tag_name` | TEXT    | PRIMARY KEY (composite), FK → `tags.name` | Reference to tag  |

The composite `(idea_id, tag_name)` pair is the primary key, preventing duplicate associations.

---

### `book_authors`

Many-to-many join table between `books` and `users`. Records which users are authors/participants of a book.

| Column    | Type    | Constraints                               | Description       |
|-----------|---------|-------------------------------------------|-------------------|
| `book_id` | INTEGER | PRIMARY KEY (composite), FK → `books.id`  | Reference to book |
| `user_id` | INTEGER | PRIMARY KEY (composite), FK → `users.id`  | Reference to user |

The composite `(book_id, user_id)` pair is the primary key, preventing duplicate authorship entries.

> **Access control:** book authorship is the authorisation gate for creating impact comments — see `impact_comments` below.

---

### `idea_votes`

Records upvotes (+1) and downvotes (−1) cast by users on ideas. A user may cast at most one vote per idea (upsert semantic).

| Column       | Type    | Constraints                                   | Description               |
|--------------|---------|-----------------------------------------------|---------------------------|
| `id`         | INTEGER | PRIMARY KEY AUTOINCREMENT                     | Surrogate key             |
| `idea_id`    | INTEGER | NOT NULL, FK → `ideas.id` ON DELETE CASCADE   | Voted idea                |
| `user_id`    | INTEGER | NOT NULL, FK → `users.id` ON DELETE CASCADE   | Voter                     |
| `value`      | INTEGER | NOT NULL, CHECK (value IN (-1, 1))            | +1 upvote, −1 downvote    |
| `created_at` | TEXT    | NOT NULL DEFAULT (datetime('now'))            | Timestamp (UTC, ISO-8601) |

`UNIQUE (idea_id, user_id)` prevents duplicate votes; the `ON CONFLICT DO UPDATE` clause flips the value on a second call.

---

### `impact_comments`

Free-text annotations attached to ideas by book authors. A user may post multiple comments on the same idea (no uniqueness constraint). Only users listed in `book_authors` for the idea's book may create comments (enforced at the API layer — HTTP 403 otherwise).

| Column       | Type    | Constraints                                   | Description                  |
|--------------|---------|-----------------------------------------------|------------------------------|
| `id`         | INTEGER | PRIMARY KEY AUTOINCREMENT                     | Surrogate key                |
| `idea_id`    | INTEGER | NOT NULL, FK → `ideas.id` ON DELETE CASCADE   | Commented idea               |
| `user_id`    | INTEGER | NOT NULL, FK → `users.id` ON DELETE CASCADE   | Comment author               |
| `content`    | TEXT    | NOT NULL                                      | Text content of the comment  |
| `created_at` | TEXT    | NOT NULL DEFAULT (datetime('now'))            | Timestamp (UTC, ISO-8601)    |

Cascade behaviour: deleting an idea or a user automatically removes all associated impact comments.

---

## Entity-Relationship Diagram

```
users
  id ──────────────┬──────────────────────────┬─────────────────────────┐
  username         │                          │                         │
  email            │ owner_id (FK)            │ user_id (FK)            │ user_id (FK)
  hashed_password  │                          │                         │
  is_admin         │                 book_authors              impact_comments
                   │                   book_id ─────────────┐   idea_id ──┐
ideas              │                   user_id ─────────────┘   user_id   │
  id ◄─────────────┘                                             content  │
  title                                                          created_at│
  content                                                                  │
  book_id ── FK → books                                                    │
                    books                                                  │
                      id ◄── book_id (book_authors, ideas) ───────────────┘
                      title                                    (via ideas.book_id)

relations (junction)          tags            idea_votes
  idea_id ─── FK → ideas.id   name (PK)        idea_id ─── FK → ideas.id (CASCADE)
  tag_name ── FK → tags.name                   user_id ─── FK → users.id (CASCADE)
                                               value CHECK(-1, 1)
                                               UNIQUE (idea_id, user_id)
```

---

## Constraints & Integrity

- **`idea_votes` and `impact_comments`** use `ON DELETE CASCADE` — rows are removed automatically when the parent idea or user is deleted.
- **Other tables** have no `ON DELETE CASCADE`. Deleting a `user`, `book`, or `tag` while related rows exist in `ideas`, `book_authors`, or `relations` will violate foreign key constraints if FK enforcement is enabled at connection time (SQLite requires `PRAGMA foreign_keys = ON`).
- Duplicate tags and duplicate relations are silently swallowed at the application layer.
- `book_id` is required (`NOT NULL`) when creating an idea; the API returns HTTP 400 if omitted.
- Creating an impact comment requires the requesting user to be in `book_authors` for the idea's book — enforced in the API layer, returning HTTP 403 otherwise.

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

| Purpose                             | Tables touched                                                   |
|-------------------------------------|------------------------------------------------------------------|
| All ideas with tags                 | `ideas` LEFT JOIN `relations`                                    |
| Ideas owned by a user               | `ideas` JOIN `relations` JOIN `users`                            |
| Ideas filtered by tags              | `ideas` JOIN `relations` JOIN `tags`                             |
| Tags for a given idea               | `relations` WHERE `idea_id = ?`                                  |
| User lookup for TOTP verify         | `users` WHERE `email = ?`                                        |
| Owner lookup when adding idea       | `users` WHERE `email = ?`                                        |
| Authors of a book                   | `users` JOIN `book_authors` WHERE `book_id`                      |
| Check if user is a book author      | `book_authors` JOIN `users` WHERE `book_id` AND `email`          |
| Impact comments for an idea         | `impact_comments` JOIN `users` WHERE `idea_id`                   |
| All impact comments for a book      | `impact_comments` JOIN `ideas` JOIN `users` WHERE `ideas.book_id`|
