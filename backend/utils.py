
def format_text(
    name: str,
    description: str,
    tags: list[str],
    comments: list[str] | None = None,
) -> str:
    """Build a single document string optimised for embedding.

    The title appears twice (start + before description) to amplify its
    weight in the embedding vector.  Tags use natural comma separators.
    Comments are appended last so they are the first tokens truncated
    when the sequence exceeds the model's max length.
    """
    tags_str = ", ".join(tags)
    parts = [
        f"{name}.",
        f"Tags: {tags_str}.",
        f"{name}: {description}",
    ]
    if comments:
        parts.append(f"Comments: {' | '.join(comments)}")
    return " ".join(parts)
