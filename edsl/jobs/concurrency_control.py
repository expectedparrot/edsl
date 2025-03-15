"""
Concurrency control for EDSL jobs.

This module provides utilities for managing concurrent execution of interviews,
with adaptive controls based on system resources and runtime behavior.
"""
import os
import psutil
import asyncio
from typing import Optional, Type, TYPE_CHECKING, List, Dict, Any
import multiprocessing

if TYPE_CHECKING:
    from ..interviews import Interview


class ConcurrencyManager:
    """
    Manager for concurrent execution of interviews.
    
    This class determines appropriate concurrency levels based on system
    resources and provides utilities for running interviews concurrently
    with controlled parallelism.
    """
    
    # Default maximum concurrency if not otherwise determined
    DEFAULT_MAX_CONCURRENT = 10
    
    @classmethod
    def get_max_concurrent(cls) -> int:
        """
        Get the maximum number of concurrent interviews to run.
        
        This method determines an appropriate concurrency level based on
        available CPU cores, configured limits, and system load.
        
        Returns:
            int: The maximum number of concurrent interviews
        """
        # Check if explicitly set in environment
        from ..config import Config
        config = Config()
        if hasattr(config, 'EDSL_MAX_CONCURRENT_TASKS'):
            env_value = config.EDSL_MAX_CONCURRENT_TASKS
            if env_value and env_value.isdigit():
                return int(env_value)
        
        # Otherwise, use adaptive approach based on CPU cores
        try:
            # Get number of CPU cores
            cpu_count = multiprocessing.cpu_count()
            
            # For very small systems, use at least 2 cores for concurrency
            # For larger systems, use 75% of available cores
            if cpu_count <= 2:
                return max(2, cpu_count)
            else:
                return max(2, int(cpu_count * 0.75))
        except:
            # If we can't determine CPU count, use default
            return cls.DEFAULT_MAX_CONCURRENT
    
    @classmethod
    async def run_concurrent_interviews(
        cls, 
        interviews: List["Interview"],
        process_interview,
        stop_on_exception: bool = False,
        chunk_size: Optional[int] = None
    ) -> List[Any]:
        """
        Run interviews concurrently with controlled parallelism.
        
        Parameters:
            interviews: List of interviews to run
            process_interview: Async function to process a single interview
            stop_on_exception: Whether to stop if an exception occurs
            chunk_size: Number of interviews to process in each chunk
                        (if None, will use get_max_concurrent)
                        
        Returns:
            List[Any]: Results from processing each interview
        """
        max_concurrent = chunk_size or cls.get_max_concurrent()
        results = []
        
        # Process interviews in chunks to control memory usage
        for i in range(0, len(interviews), max_concurrent):
            chunk = interviews[i : i + max_concurrent]
            
            # Create tasks for this chunk
            tasks = [
                asyncio.create_task(process_interview(interview, idx))
                for idx, interview in enumerate(chunk, start=i)
            ]
            
            try:
                # Wait for all tasks in the chunk to complete
                chunk_results = await asyncio.gather(
                    *tasks,
                    return_exceptions=not stop_on_exception
                )
                
                # Filter out None results (failed interviews)
                results.extend([r for r in chunk_results if r is not None])
                
            except Exception as e:
                if stop_on_exception:
                    raise
            finally:
                # Clean up any remaining tasks
                for task in tasks:
                    if not task.done():
                        task.cancel()
        
        return results
    
    @staticmethod
    def get_system_load() -> Dict[str, float]:
        """
        Get current system load information.
        
        This method collects information about CPU, memory, and I/O load
        that can be used for adaptive concurrency decisions.
        
        Returns:
            Dict[str, float]: System load metrics
        """
        try:
            # Get current CPU and memory usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_percent = psutil.virtual_memory().percent
            
            return {
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent
            }
        except:
            # If we can't get system info, return default values
            return {
                "cpu_percent": 50.0,
                "memory_percent": 50.0
            }
    
    @classmethod
    def should_reduce_concurrency(cls) -> bool:
        """
        Determine if concurrency should be reduced based on system load.
        
        This method checks if the system is under high load and concurrency
        should be reduced to avoid performance degradation.
        
        Returns:
            bool: True if concurrency should be reduced, False otherwise
        """
        load = cls.get_system_load()
        
        # If CPU or memory usage is very high, reduce concurrency
        return load["cpu_percent"] > 90 or load["memory_percent"] > 85