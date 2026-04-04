import os
import json
import logging


logger = logging.getLogger("uvicorn.error")

def set_env_var() -> None:
    """Set all configuration variables as environment variables."""
    try:
        # Set all config variables as environment variables.
        # Use setdefault so that values pre-set by tests (or the host environment)
        # are not overwritten.
        os.environ.setdefault('CHROMA_DB', os.path.join(os.path.dirname(__file__), "data", "embeddings"))
        os.environ.setdefault('NAME_DB', os.path.join(os.path.dirname(__file__), "data", "knowledge.db"))
        os.environ.setdefault('TOC_CACHE_PATH', os.path.join(os.path.dirname(__file__), "data", "toc.json"))
        
        # Load origins from site.json
        site_json_path = os.path.join(os.path.dirname(__file__), "data", "site.json")
        if os.path.exists(site_json_path):
            with open(site_json_path, 'r') as f:
                site_data = json.load(f)
                if 'origins' in site_data:
                    # Convert origins list to comma-separated string for environment variable
                    origins_string = ",".join(site_data['origins'])
                    os.environ['ALLOWED_ORIGINS'] = origins_string
                    logger.info(f"Loaded origins from site.json: {origins_string}")
                else:
                    logger.warning("No 'origins' key found in site.json")
        else:
            logger.warning("site.json file not found")

        logger.info("All configuration variables have been set as environment variables")
    except Exception as e:
        logger.error(f"Error setting environment variables: {str(e)}")
        raise
