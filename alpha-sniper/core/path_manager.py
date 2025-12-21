"""
Centralized storage path management with atomic writes and fallback logic.
Ensures bot never crashes due to permission issues.
"""

import os
import json
import tempfile
import shutil
from pathlib import Path
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


class PathManager:
    """
    Manages all persistent storage with robust fallback and atomic writes.

    Priority:
    1. ALPHA_SNIPER_DATA_DIR env var
    2. ./data (relative to project root)
    3. ~/.alpha-sniper/data
    """

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).parent.parent.parent
        self.data_dir = self._resolve_data_dir()
        self._ensure_writable()

    def _resolve_data_dir(self) -> Path:
        """Resolve data directory with 3-tier fallback."""
        # Priority 1: Environment variable
        if env_dir := os.getenv('ALPHA_SNIPER_DATA_DIR'):
            path = Path(env_dir).expanduser().resolve()
            if self._test_writable(path):
                logger.info(f"Using data dir from env: {path}")
                return path
            logger.warning(f"ALPHA_SNIPER_DATA_DIR not writable: {path}")

        # Priority 2: ./data relative to project
        local_data = self.project_root / 'data'
        if self._test_writable(local_data):
            logger.info(f"Using local data dir: {local_data}")
            return local_data

        # Priority 3: Home directory fallback
        home_data = Path.home() / '.alpha-sniper' / 'data'
        if self._test_writable(home_data):
            logger.info(f"Using home data dir: {home_data}")
            return home_data

        # Last resort: try local anyway (will fail later if truly not writable)
        logger.error(f"No writable data dir found, using {local_data} (may fail)")
        return local_data

    def _test_writable(self, path: Path) -> bool:
        """Test if directory is writable."""
        try:
            path.mkdir(parents=True, exist_ok=True)
            test_file = path / '.write_test'
            test_file.write_text('test')
            test_file.unlink()
            return True
        except (OSError, PermissionError):
            return False

    def _ensure_writable(self):
        """Ensure data directory exists and is writable."""
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            # Create subdirectories
            (self.data_dir / 'positions').mkdir(exist_ok=True)
            (self.data_dir / 'metrics').mkdir(exist_ok=True)
            (self.data_dir / 'quarantine').mkdir(exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create data directories: {e}")

    def get_path(self, category: str, filename: str) -> Path:
        """Get full path for a file in a category."""
        return self.data_dir / category / filename

    def write_json(self, category: str, filename: str, data: Any) -> bool:
        """
        Atomic JSON write with error handling.
        Returns True on success, False on failure (never crashes).
        """
        target_path = self.get_path(category, filename)

        try:
            # Write to temp file first
            with tempfile.NamedTemporaryFile(
                mode='w',
                dir=target_path.parent,
                delete=False,
                suffix='.tmp'
            ) as tf:
                json.dump(data, tf, indent=2)
                temp_path = Path(tf.name)

            # Atomic rename
            shutil.move(str(temp_path), str(target_path))
            return True

        except Exception as e:
            logger.warning(f"Failed to write {target_path}: {e}")
            # Clean up temp file if it exists
            try:
                if 'temp_path' in locals():
                    temp_path.unlink(missing_ok=True)
            except:
                pass
            return False

    def read_json(self, category: str, filename: str, default: Any = None) -> Any:
        """Read JSON file with default fallback."""
        path = self.get_path(category, filename)
        try:
            if path.exists():
                with open(path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read {path}: {e}")

        return default if default is not None else {}


# Global instance
_path_manager = None

def get_path_manager() -> PathManager:
    """Get or create global PathManager instance."""
    global _path_manager
    if _path_manager is None:
        _path_manager = PathManager()
    return _path_manager
