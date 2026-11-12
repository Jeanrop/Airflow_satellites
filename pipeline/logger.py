import logging


def setup_logging(log_path: str = "journal.log") -> None:
    """Log to both the console and a file, with timestamps."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    # httpx logs every request at INFO level, which is noisy
    logging.getLogger("httpx").setLevel(logging.WARNING)