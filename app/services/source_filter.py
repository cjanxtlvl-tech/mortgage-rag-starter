"""Source filtering to determine which files are appropriate for public display."""


# Internal control and routing files that should NOT appear in public responses
INTERNAL_SOURCES = {
    "rasa_rag_intent_routing_dataset.json",
    "prompts.json",
    "config.json",
    "settings.json",
    "debug.json",
    "temp",
    ".temp",
}

# User-facing knowledge datasets that ARE appropriate for public display
PUBLIC_DATASETS = {
    "mortgage_basics.json",
    "mortgage_knowledge_base.json",
    "investor_dscr_advanced_dataset.json",
    "mortgage_additional_training.json",
    "mortgage_conversion_dataset.json",
}


def is_display_source(source_file: str) -> bool:
    """
    Determine if a source file should be displayed to end users.
    
    Returns True only for real knowledge datasets.
    Returns False for internal control files, configs, prompts, or debug data.
    
    Args:
        source_file: The source filename (e.g., "mortgage_basics.json")
        
    Returns:
        bool: True if the source is appropriate for public display
    """
    if not source_file:
        return False

    source_lower = source_file.strip().lower()

    # Explicit internal blocklist
    if source_lower in {s.lower() for s in INTERNAL_SOURCES}:
        return False

    # If it's in the public dataset list, allow it
    if source_lower in {s.lower() for s in PUBLIC_DATASETS}:
        return True

    # Block files starting with underscore or dot (config/internal pattern)
    if source_lower.startswith(("_", ".")):
        return False

    # Block common internal patterns
    internal_patterns = ("prompt", "config", "debug", "internal", "control", "routing")
    if any(pattern in source_lower for pattern in internal_patterns):
        return False

    # Default: block unknown files for safety
    return False


def filter_sources(sources: list[str]) -> list[str]:
    """
    Filter a list of sources to only include user-facing datasets.
    
    Args:
        sources: List of source file names
        
    Returns:
        list[str]: Filtered list containing only appropriate public sources
    """
    return [s for s in sources if is_display_source(s)]
