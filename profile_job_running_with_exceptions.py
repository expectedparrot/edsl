from edsl import Model, QuestionFreeText, ScenarioList, Cache 
from memory_profiler import profile
from edsl.language_models.price_manager import PriceManager
from edsl.language_models.registry import RegisterLanguageModelsMeta
import gc
import psutil
import objgraph
import inspect

def print_memory_info():
    """Print detailed memory usage information."""
    # Get process memory info
    process = psutil.Process()
    mem_info = process.memory_info()
    print(f"RSS Memory: {mem_info.rss / (1024 * 1024):.2f} MB")
    print(f"VMS Memory: {mem_info.vms / (1024 * 1024):.2f} MB")
    
    # Count objects of interest
    types_to_count = [
        "Results", "SQLList", "Cache", "PriceManager", 
        "Engine", "Session", "Connection", "ScenarioList"
    ]
    
    for obj_type in types_to_count:
        try:
            count = len(objgraph.by_type(obj_type))
            print(f"{obj_type} objects: {count}")
            
            # For problematic types, show what's referencing them
            if obj_type in ["Engine", "Connection", "SQLList", "ScenarioList"] and count > 0:
                print(f"  Finding what's keeping {obj_type} alive:")
                objects = objgraph.by_type(obj_type)
                if objects:
                    for i, obj in enumerate(objects[:2]):  # Look at first two instances
                        print(f"  Object {i+1}:")
                        
                        # For SQLList, try to identify what it's for
                        if obj_type == "SQLList":
                            # Try to get context about this SQLList
                            db_path = getattr(obj, 'db_path', 'unknown')
                            memory_only = getattr(obj, 'is_memory_only', 'unknown')
                            print(f"    SQLList db_path: {db_path}")
                            print(f"    SQLList is_memory_only: {memory_only}")
                            
                            # Try to see what references this SQLList
                            refs = gc.get_referrers(obj)
                            for ref in refs[:2]:  # Look at first couple of referrers
                                ref_type = type(ref).__name__
                                if ref_type == 'ScenarioList':
                                    print("    Referenced by: ScenarioList")
                                elif ref_type == 'Results':
                                    print("    Referenced by: Results")
                                elif ref_type != 'list' and ref_type != 'dict':
                                    print(f"    Referenced by: {ref_type}")
                        
                        # For ScenarioList, we need to see what's referencing it
                        if obj_type == "ScenarioList":
                            # Get all references to the ScenarioList
                            refs = gc.get_referrers(obj)
                            print(f"    Total references: {len(refs)}")
                            
                            # Analyze the referrers to see what's holding onto the ScenarioList
                            for ref_idx, ref in enumerate(refs[:5]):  # Look at first 5 referrers
                                ref_type = type(ref).__name__
                                ref_id = id(ref)
                                print(f"    Referrer {ref_idx+1}: Type={ref_type}, ID={ref_id}")
                                
                                # For frame objects, print the filename and line number
                                if ref_type == 'frame':
                                    frame_info = inspect.getframeinfo(ref)
                                    print(f"      Frame: {frame_info.filename}:{frame_info.lineno}")
                                
                                # For dictionaries, see if they're from function locals
                                if ref_type == 'dict':
                                    # Check if it's local variables for some function
                                    dict_refs = gc.get_referrers(ref)
                                    for dict_ref in dict_refs[:2]:
                                        dict_ref_type = type(dict_ref).__name__
                                        if dict_ref_type == 'frame':
                                            frame_info = inspect.getframeinfo(dict_ref)
                                            print(f"      Dict from frame: {frame_info.filename}:{frame_info.lineno}")
                                        else:
                                            print(f"      Dict from: {dict_ref_type}")
                                
                                # For frames or other container objects holding the ScenarioList
                                if hasattr(ref, '__dict__'):
                                    # Find which attribute holds the ScenarioList
                                    for attr_name, attr_val in ref.__dict__.items():
                                        if attr_val is obj:
                                            print(f"      Held in attribute: {attr_name}")
                        
                        # Find backref chains for all types
                        try:
                            chains = objgraph.find_backref_chain(obj, objgraph.is_proper_module, max_depth=5)
                            if chains:
                                print("    Reference chain:")
                                for j, node in enumerate(chains):
                                    print(f"      {j}: {type(node).__name__}")
                            else:
                                print("    No reference chains found")
                        except Exception as e:
                            print(f"    Error finding references: {e}")
        except Exception as e:
            print(f"Error analyzing {obj_type}: {e}")
    
    # Force a full collection
    gc.collect()

@profile
def run_model_with_exceptions(n, throw_exception = True):
    print(f"Running model with {n} scenarios")
    
    # Use the context manager pattern for proper resource cleanup
    with Cache() as cache:
        m = Model("test", canned_response="Hello", throw_exception=throw_exception, exception_probability=0.5)
        
        q = QuestionFreeText(question_text="Do you like {{ number}}", question_name="cool_question")
        
        # Create ScenarioList
        s = ScenarioList.from_list("number", list(range(n)))
        
        # Run the job
        results = q.by(s).by(m).run(disable_remote_inference=True, cache=cache)
        
        # Use the comprehensive cleanup function
        comprehensive_cleanup(results=results, scenario_list=s)
    
    # Run memory diagnostics
    print("\nMemory diagnostics after comprehensive cleanup:")
    print_memory_info()
    
    return None

@profile
def run_standard_cleanup(n):
    """Run with just basic cleanup for comparison."""
    print(f"\nRunning with standard cleanup ({n} scenarios)")
    
    with Cache() as cache:
        m = Model("test", canned_response="Hello")
        q = QuestionFreeText(question_text="Do you like {{ number}}", question_name="cool_question")
        s = ScenarioList.from_list("number", list(range(n)))
        
        results = q.by(s).by(m).run(disable_remote_inference=True, cache=cache)
        
        # Standard cleanup - just delete without breaking references
        print("Standard cleanup - just deleting results")
        del results
        
        # Keep the ScenarioList for later to show memory leak
        print("NOT cleaning up ScenarioList (to demonstrate leak)")
        # We don't delete s or clean it up here to show the memory leak!
    
    print("Standard reset of PriceManager")
    PriceManager.reset()
    
    print("Standard clearing of language model registry")
    RegisterLanguageModelsMeta.clear_registry()
    
    print("Standard garbage collection")
    import gc
    gc.collect()
    
    # Run memory diagnostics
    print("\nMemory diagnostics after standard cleanup (with expected ScenarioList leak):")
    print_memory_info()

def comprehensive_cleanup(results=None, scenario_list=None):
    """Thoroughly clean up both Results and ScenarioList objects.
    
    This function ensures proper memory cleanup by:
    1. Cleaning up the Results object (if provided)
    2. Cleaning up the ScenarioList object (if provided)
    3. Resetting global singletons like PriceManager
    4. Forcing garbage collection
    5. Running explicit collection passes to eliminate lingering references
    
    Args:
        results: Optional Results object to clean up
        scenario_list: Optional ScenarioList object to clean up
    """
    print("\nPerforming comprehensive memory cleanup...")
    
    # 1. First clean up Results object
    if results is not None:
        print("1. Cleaning up Results object")
        
        # Call explicit memory cleanup first
        results.free_memory()
        
        # Explicitly dispose SQLAlchemy engine if available
        if hasattr(results.data, 'engine'):
            print("  Disposing Results SQLAlchemy engine")
            results.data.engine.dispose()
        
        # Break circular references by clearing major attributes
        print("  Breaking Results circular references")
        results.task_history = None
        results.cache = None
        results.survey = None
        results.data = None  # Clear this last after using engine
        
        # Now delete the results object
        del results
    
    # 2. Clean up ScenarioList object
    if scenario_list is not None:
        print("2. Cleaning up ScenarioList object")
        
        # Save a reference to the SQLList for cleanup
        sql_list = None
        if hasattr(scenario_list, 'data'):
            sql_list = scenario_list.data
            
            if hasattr(sql_list, 'engine'):
                print("  Disposing ScenarioList SQLAlchemy engine")
                sql_list.engine.dispose()
            
            print("  Breaking ScenarioList circular references")
            # Break all potential circular references to ScenarioList
            scenario_list.data = None
            
            # Clear any other attributes that might hold references
            if hasattr(scenario_list, 'codebook'):
                scenario_list.codebook = None
                
            # If ScenarioList has any other attributes, clear them too
            for attr_name in list(vars(scenario_list).keys()):
                setattr(scenario_list, attr_name, None)
        
        # Run a garbage collection pass
        gc.collect()
        
        # Delete ScenarioList first to remove its references
        del scenario_list
        
        # Now clean up the SQLList separately if we had one
        if sql_list is not None:
            print("  Cleaning up detached SQLList")
            if hasattr(sql_list, 'free_memory'):
                sql_list.free_memory()
            
            # Force cleanup of SQLList resources
            if hasattr(sql_list, '__cleanup'):
                try:
                    sql_list.__cleanup()
                except Exception:
                    pass
                
            # Remove any other references
            for attr_name in list(vars(sql_list).keys()):
                setattr(sql_list, attr_name, None)
            
            # Now delete the SQLList object too
            del sql_list
    
    # 3. Reset the PriceManager singleton to clean up resources
    print("3. Resetting global singletons")
    print("  Resetting PriceManager")
    PriceManager.reset()
    
    # Clear the language model registry to prevent accumulation
    print("  Clearing language model registry")
    RegisterLanguageModelsMeta.clear_registry()
    
    # 4. Force garbage collection to release any lingering references
    print("4. Forcing multiple garbage collection passes")
    # Run multiple collection passes to clear all references
    for i in range(3):
        gc.collect()
        
    # 5. Explicitly hunt for ScenarioList objects and break references
    scenario_lists = objgraph.by_type('ScenarioList')
    if scenario_lists:
        print(f"  Found {len(scenario_lists)} lingering ScenarioList objects")
        for sl in scenario_lists:
            # Break any attributes
            for attr_name in list(vars(sl).keys()):
                setattr(sl, attr_name, None)
                
        # Run additional collection after breaking references
        gc.collect()

def explicit_scenario_cleanup():
    """Run test with explicit ScenarioList cleanup."""
    print("\nTesting with explicit ScenarioList cleanup")
    
    # Create a ScenarioList
    s = ScenarioList.from_list("number", list(range(20)))
    print(f"Created ScenarioList with {len(s)} items")
    
    # Get info about its SQLList if it has one
    if hasattr(s, 'data') and hasattr(s.data, 'engine'):
        print(f"ScenarioList has SQLList with engine: {s.data.engine}")
        
    # Use our comprehensive cleanup function
    comprehensive_cleanup(scenario_list=s)
    
    # Check memory
    print("\nMemory after explicit ScenarioList cleanup:")
    print_memory_info()

if __name__ == "__main__":
    # Initial memory state
    print("Initial memory state:")
    print_memory_info()
    
    # First run with standard cleanup
    run_standard_cleanup(500)
    
    # Then run with improved cleanup
    run_model_with_exceptions(500, throw_exception=False)
    
    # Test explicit ScenarioList cleanup
    explicit_scenario_cleanup()
    
    # Final memory check
    print("\n--- Final memory state after all tests ---")
    print_memory_info()
 