import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class BackgroundTaskProcessor:
    """
    Simple background task processor using ThreadPoolExecutor.
    No external dependencies (Redis/Celery) required.
    """
    
    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="bg_task")
        self.tasks = {}
        self.lock = threading.Lock()
        
    def submit_task(self, task_id: str, func: Callable, *args, **kwargs) -> None:
        """
        Submit a task for background execution.
        
        Args:
            task_id: Unique identifier for the task
            func: Function to execute
            *args, **kwargs: Arguments to pass to the function
        """
        def wrapped_task():
            try:
                logger.info(f"Starting background task: {task_id}")
                result = func(*args, **kwargs)
                
                with self.lock:
                    self.tasks[task_id] = {
                        'status': 'completed',
                        'result': result,
                        'error': None
                    }
                logger.info(f"Completed background task: {task_id}")
                return result
                
            except Exception as e:
                logger.error(f"Background task {task_id} failed: {e}", exc_info=True)
                with self.lock:
                    self.tasks[task_id] = {
                        'status': 'failed',
                        'result': None,
                        'error': str(e)
                    }
                raise
        
        with self.lock:
            self.tasks[task_id] = {
                'status': 'processing',
                'result': None,
                'error': None
            }
        
        future = self.executor.submit(wrapped_task)
        return future
    
    def get_task_status(self, task_id: str) -> dict:
        """
        Get the status of a background task.
        
        Returns:
            dict with keys: status ('pending', 'processing', 'completed', 'failed'),
                           result (if completed), error (if failed)
        """
        with self.lock:
            return self.tasks.get(task_id, {'status': 'not_found', 'result': None, 'error': None})
    
    def shutdown(self, wait: bool = True):
        """Shutdown the executor."""
        self.executor.shutdown(wait=wait)


# Global instance
_background_processor = None

def get_background_processor() -> BackgroundTaskProcessor:
    """Get or create the global background task processor."""
    global _background_processor
    if _background_processor is None:
        _background_processor = BackgroundTaskProcessor(max_workers=4)
    return _background_processor
