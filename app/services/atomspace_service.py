import logging
import os
from typing import List, Any, Optional
from hyperon import MeTTa

logger = logging.getLogger(__name__)

class AtomSpaceService:
    def __init__(self):
        try:
            self.metta = MeTTa()
            logger.info("AtomSpaceService initialized with Hyperon MeTTa interpreter.")
        except Exception as e:
            logger.error(f"Failed to initialize AtomSpaceService: {e}")
            raise

    def execute_script(self, script):
        try:
            results = self.metta.run(script)
            #for API compatibility
            return [[str(atom) for atom in result] for result in results]
        except Exception as e:
            logger.error(f"Execution error in MeTTa script: {e}")
            raise

    def load_metta_file(self, file_path):
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return False

        try:
            self.metta.run(f'!(import! "{file_path}")')
            logger.info(f"Loaded MeTTa file: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load MeTTa file {file_path}: {e}")
            return False

atomspace_service = AtomSpaceService()
