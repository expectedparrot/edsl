#!/usr/bin/env python3
"""
Debug script for the Unified Results Inspector Widget

This script helps diagnose issues with Results object processing.
"""

import sys
sys.path.append('/Users/johnhorton/tools/ep/edsl')

from edsl.widgets.unified_results_inspector import UnifiedResultsInspectorWidget

def debug_results_object(results):
    """Debug the Results object to see what's available."""
    
    print("🔍 Debugging Results Object")
    print("=" * 50)
    
    print(f"📋 Basic Info:")
    print(f"   - Type: {type(results)}")
    print(f"   - Length: {len(results) if hasattr(results, '__len__') else 'N/A'}")
    print(f"   - Has _summary method: {hasattr(results, '_summary')}")
    print(f"   - Has to_dict method: {hasattr(results, 'to_dict')}")
    print(f"   - Has to_dataset method: {hasattr(results, 'to_dataset')}")
    
    # Try to get summary
    if hasattr(results, '_summary'):
        try:
            summary = results._summary()
            print(f"\n📊 Summary:")
            for key, value in summary.items():
                print(f"   - {key}: {value}")
        except Exception as e:
            print(f"   ❌ Error getting summary: {e}")
    
    # Try to get dict representation
    if hasattr(results, 'to_dict'):
        try:
            results_dict = results.to_dict()
            print(f"\n📁 Dict Structure:")
            if isinstance(results_dict, dict):
                for key, value in results_dict.items():
                    if isinstance(value, (list, dict)):
                        print(f"   - {key}: {type(value)} (length: {len(value) if hasattr(value, '__len__') else 'N/A'})")
                    else:
                        print(f"   - {key}: {value}")
                        
                # Check survey structure
                if 'survey' in results_dict:
                    survey = results_dict['survey']
                    print(f"\n🔍 Survey Details:")
                    if isinstance(survey, dict) and 'questions' in survey:
                        questions = survey['questions']
                        print(f"   - Questions: {len(questions)} found")
                        if questions:
                            print(f"   - First question keys: {list(questions[0].keys()) if isinstance(questions[0], dict) else 'Not a dict'}")
                    else:
                        print(f"   - Survey structure: {type(survey)}")
                        
                # Check data structure  
                if 'data' in results_dict:
                    data = results_dict['data']
                    print(f"\n🔍 Data Details:")
                    print(f"   - Data type: {type(data)}")
                    print(f"   - Data length: {len(data) if hasattr(data, '__len__') else 'N/A'}")
                    if isinstance(data, list) and data:
                        print(f"   - First data item keys: {list(data[0].keys()) if isinstance(data[0], dict) else 'Not a dict'}")
                        
            else:
                print(f"   - Dict is type: {type(results_dict)}")
        except Exception as e:
            print(f"   ❌ Error getting dict: {e}")
            import traceback
            traceback.print_exc()
    
    # Try to get dataset
    if hasattr(results, 'to_dataset'):
        try:
            dataset = results.to_dataset()
            print(f"\n📈 Dataset Structure:")
            print(f"   - Dataset type: {type(dataset)}")
            if hasattr(dataset, 'relevant_columns'):
                try:
                    columns = dataset.relevant_columns()
                    print(f"   - Columns: {len(columns)} found")
                    if columns:
                        print(f"   - First 5 columns: {columns[:5]}")
                except Exception as e:
                    print(f"   - Error getting columns: {e}")
            if hasattr(dataset, 'to_dicts'):
                try:
                    dicts = dataset.to_dicts(remove_prefix=False)
                    print(f"   - Records: {len(dicts)} found")
                    if dicts:
                        print(f"   - First record keys: {list(dicts[0].keys())[:5] if isinstance(dicts[0], dict) else 'Not a dict'}")
                except Exception as e:
                    print(f"   - Error getting dicts: {e}")
        except Exception as e:
            print(f"   ❌ Error getting dataset: {e}")

def test_widget_with_debug(results):
    """Test the widget creation with detailed debugging."""
    
    print("\n🎨 Testing Widget Creation")
    print("=" * 50)
    
    try:
        # Create widget
        widget = UnifiedResultsInspectorWidget(obj=results)
        print("✅ Widget object created")
        
        # Check widget properties
        print(f"\n🔍 Widget Properties:")
        print(f"   - Object stored: {widget.object is not None}")
        print(f"   - Object type: {type(widget.object)}")
        print(f"   - Data stored: {widget.data is not None if hasattr(widget, 'data') else 'No data attribute'}")
        
        # Check traitlets
        print(f"\n🔍 Widget Traitlets:")
        print(f"   - results_data: {len(widget.results_data) if widget.results_data else 'Empty/None'}")
        print(f"   - paginated_results: {len(widget.paginated_results) if widget.paginated_results else 'Empty/None'}")
        print(f"   - analysis_data: {len(widget.analysis_data) if widget.analysis_data else 'Empty/None'}")
        
        # Try to manually trigger data processing
        print(f"\n🔄 Manual Data Processing:")
        try:
            # Check if widget has the object
            if widget.object:
                print("✅ Widget has object, trying to process data...")
                
                # Check if it has data attribute (from base class)
                if hasattr(widget, 'data') and widget.data:
                    print("✅ Widget has data attribute")
                    result = widget._process_object_data()
                    print(f"✅ Data processing completed: {result is not None}")
                else:
                    print("⚠️ Widget missing data attribute, trying to set...")
                    # Try to set data manually
                    if hasattr(widget.object, 'to_dict'):
                        widget.data = widget.object.to_dict()
                        print("✅ Data set manually")
                        result = widget._process_object_data()
                        print(f"✅ Data processing completed: {result is not None}")
                    else:
                        print("❌ Cannot get dict representation of object")
            else:
                print("❌ Widget has no object")
                
        except Exception as e:
            print(f"❌ Error in manual processing: {e}")
            import traceback
            traceback.print_exc()
            
        # Final state check
        print(f"\n🎯 Final Widget State:")
        print(f"   - results_data populated: {bool(widget.results_data)}")
        print(f"   - paginated_results populated: {bool(widget.paginated_results)}")  
        print(f"   - analysis_data populated: {bool(widget.analysis_data)}")
        
        if widget.results_data:
            print(f"   - results_data keys: {list(widget.results_data.keys())}")
            if 'data' in widget.results_data:
                print(f"   - results_data.data length: {len(widget.results_data['data'])}")
        
        return widget
        
    except Exception as e:
        print(f"❌ Error creating widget: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Main debugging function."""
    
    print("🚀 EDSL Unified Results Inspector - Debug Mode")
    print("=" * 60)
    
    print("\nℹ️ Please create your Results object and pass it to this function:")
    print("   debug_results_object(your_results)")
    print("   test_widget_with_debug(your_results)")
    
    return debug_results_object, test_widget_with_debug

if __name__ == "__main__":
    debug_results_object, test_widget_with_debug = main()
    print("\n💡 Functions ready:")
    print("   - debug_results_object(results)")  
    print("   - test_widget_with_debug(results)")