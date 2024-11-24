import bpy
import importlib
import sys

bl_info = {
    "name": "Destiny Importer",
    "author": "DeltaDesigns, Montague/Monteven",
    "version": (1, 2, 5),
    "blender": (4, 0, 0),
    "location": "File > Import",
    "description": "Import Destiny rips from Charm",
    "category": "Import",
    "package": "destiny_importer"
    }

current_package_prefix = f"{__name__}."
for name, module in sys.modules.copy().items():
    if name.startswith(current_package_prefix):
        print(f"Reloading {name}")
        importlib.reload(module)

def register():
    from .destiny_importer import register_importer
    register_importer()

def unregister():
    from .destiny_importer import unregister_importer
    unregister_importer()