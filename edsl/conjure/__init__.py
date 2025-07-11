import sys
from types import ModuleType
import subprocess

class OptionalDependencyModule(ModuleType):
    """Module that prompts to install optional dependency."""
    
    def __init__(self):
        super().__init__('edsl.conjure')
        self._real_module = None
        self._github_url = "git+https://github.com/expectedparrot/edsl-conjure.git"
    
    def __getattr__(self, name):
        if self._real_module is None:
            try:
                from conjure import conjure
                self._real_module = conjure
            except ImportError:
                print("\nedsl-conjure is not installed.")
                response = input("Install it now? [y/N]: ")
                if response.lower() in ('y', 'yes'):
                    print("Installing edsl-conjure from GitHub...")
                    # Install directly from GitHub, not via edsl[conjure]
                    subprocess.check_call([
                        sys.executable, "-m", "pip", "install", self._github_url
                    ])
                    # Force reload of importlib caches
                    import importlib
                    importlib.invalidate_caches()
                    
                    from conjure import conjure
                    self._real_module = conjure
                else:
                    raise ImportError(
                        f"Install edsl-conjure with: pip install {self._github_url}"
                    )
        
        return getattr(self._real_module, name)

# Replace this module with the lazy-loading module
sys.modules[__name__] = OptionalDependencyModule()