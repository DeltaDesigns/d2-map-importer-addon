from .__init__ import bl_info
import bpy
from bpy.props import *
import json
import os
import requests
import json
import time

from .helper_functions import *
from .materials import *
from .lights import *
from .api import *
from .decals import *

# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty, CollectionProperty, FloatProperty
from bpy.types import Operator

from multiprocessing import Process, cpu_count

# Globals for cfg related stuff
Cfg = None
FilePath = None
AssetsPath = None
Name = None
Type = "Statics"
ExportType = "Map" # Default

# Yes I shamelessly let chaptgpt help me redo a lot of this
# Fuck blender python, its awful in my very personal opinion

class ImportDestinyCfg(Operator, ImportHelper):
    bl_idname = "destiny.importer"        # Unique identifier for buttons and menu items to reference.
    bl_label = "Import .cfg"         # Display name in the interface.
    bl_options = {'UNDO', 'PRESET'}
    
    @classmethod
    def poll(self, context):
        return context.mode == 'OBJECT'

    ##--------SETTINGS--------##
    # ImportHelper mixin class uses this
    filename_ext = ".cfg"

    filter_glob: StringProperty(
            default="*.cfg;",
            options={'HIDDEN'},
            maxlen=255,  # Max internal buffer length, longer would be clamped.
            )

    files: CollectionProperty(
            name="File Path",
            type=bpy.types.OperatorFileListElement,
            )

    rename_bones: BoolProperty(
            name="Rename Bones",
            description="Renames Bones/Vertex Groups to real names if they are known",
            default=False,
            )

    merge_meshes: BoolProperty(
            name="Combine Meshes",
            description="Combine all parts of a model into one mesh.\nMay increase performace on large maps",
            default=False,
            )

    use_import_materials: BoolProperty(
            name="Import Textures",
            description="Imports textures and tries to apply them to the models.\nTextures folder must be in the same place as the .cfg you are importing",
            default=True,
            )
    
    import_lights: BoolProperty(
            name="Import Lights",
            description="Imports lights.\nSome light colors and intensities can/will be wrong",
            default=True,
            )
    
    light_intensity_override: FloatProperty(
        name="Light Intensity",
        description="Imported light intensity",
        default=10.0,  # Default value
        min=0.0,      # Minimum value
        soft_max=1000.0,  # Maximum value
    )

    override_light_color: BoolProperty(
            name="Override empty light color",
            description="Converts all lights with no color to full white",
            default=False,
            )
    
    use_terrain_dyemap_output: BoolProperty(
            name="Show Terrain Dyemaps",
            description="Use terrain dyemaps as the main shader output",
            default=False,
            )
    
    import_dyn_points: BoolProperty(
            name="Import Dynamic Points",
            description="Import empties for dynamic points (not very useful for normal users)",
            default=False,
            )
    
    import_decal_planes: BoolProperty(
            name="Import Decal Planes",
            description="Import decals as planes, this is will not actually project them on surfaces",
            default=False,
            )

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.label(text="Current Version: " + current_version)
        box.label(text="Options:")
        box.prop(self, 'rename_bones')
        box.prop(self, 'merge_meshes')
        box.prop(self, 'use_import_materials')
        box.prop(self, 'import_lights')
        box.prop(self, 'light_intensity_override')
        box.prop(self, 'override_light_color')

        box2 = layout.box()
        box2.label(text="Misc:")
        box2.prop(self, 'use_terrain_dyemap_output')
        box2.prop(self, 'import_dyn_points')
        box2.prop(self, 'import_decal_planes')
        
        if update_available:
            box = layout.box()
            box.label(text="Update available: " + latest_version)
            box.operator("wm.url_open", text="Get Latest Release").url = "https://github.com/DeltaDesigns/d2-map-importer-addon/releases/latest"

    def execute(self, context):
        global Cfg, Name, Type, ExportType, FilePath, AssetsPath
        Cfg = None
        FilePath = None
        AssetsPath = None
        Name = None
        Type = "Statics"
        ExportType = "Map"

        start_time = time.time()
        # Deselect all objects just in case
        bpy.ops.object.select_all(action='DESELECT')

        if self.files:
            dirname = os.path.dirname(self.filepath)
            FilePath = dirname
            
            file_sizes = [(file, os.path.getsize(os.path.join(dirname, file.name))) for file in self.files]
            # Import Terrain first since it needs its transforms modified outside of instancing, then do biggest to smallest
            sorted_files = sorted(file_sizes, key=lambda x: (0 if "Terrain" in x[0].name else 1, -x[1])) 

            # If a map, import every model from every cfg to save as much performance as possible
            prepare_and_process_map(self, sorted_files)
            
            # This does the actual instancing after everything needed has been imported
            process_instancing(self, sorted_files)    
            
            if self.import_lights:
                add_lights(self)

            if self.import_decal_planes:
                add_decal_planes(self)

            print("Removing Temp collection")
            hash_import_list.clear()
            collection = bpy.data.collections.get("Import_Temp")
            if collection:
                # for obj in collection.objects:
                #     bpy.data.objects.remove(obj, do_unlink=True)
                bpy.data.collections.remove(collection, do_unlink=True)

            # The final cleanup
            cleanup()

        end_time = time.time()
        elapsed_seconds = end_time - start_time

        minutes = int(elapsed_seconds // 60)
        seconds = int(elapsed_seconds % 60)
        print(f"Import finished in {minutes} minutes and {seconds} seconds")
        return {'FINISHED'} # Lets Blender know the operator finished successfully.

# Import everything model needed first for performance reasons, if importing a map
hash_import_list = []
def PrepareMapImport(self, file):
    print(f"Starting import on {ExportType} {Type}: {Name}")

    if Cfg["ExportType"] == "Map":
        if bpy.data.collections.get(str(Name)):
            print(f"Collection {str(Name)} already exists, skipping...")
            return

        collection = bpy.data.collections.get("Import_Temp")
        if not collection:
            bpy.data.collections.new("Import_Temp")
            bpy.context.scene.collection.children.link(bpy.data.collections["Import_Temp"])

        bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children["Import_Temp"]

        # Import FBX files for all meshes
        i = 1
        cleanup_factor = 0
        for mesh, instances in Cfg["Instances"].items():
            if mesh not in Cfg["Parts"] or mesh in hash_import_list:
                continue
            hash_import_list.append(mesh)
            
            if Cfg["Type"] != "Terrain":
                if not ImportFBX(self, os.path.join(f'{AssetsPath}', f"Models\\{Type}\\{mesh}.fbx")):
                    continue
            else:
                files = glob.glob(os.path.join(f'{AssetsPath}', f"Models\\{Type}\\{mesh}*.fbx"))
                for file in files:
                    if not ImportFBX(self, file):
                        continue

            print(f'{i}/{len(Cfg["Instances"])}')
            i+=1
            cleanup_factor+=1
            if cleanup_factor >= 300: # TODO this might be stupid
                #break
                cleanup()
                cleanup_factor = 0

        if self.merge_meshes: 
            CombineMeshes()

        cleanup()
        
        

# Where all the fun happens..
def DoImport(self):
    # Merge meshes/create instances for maps only
    if Is_Map(ExportType):
        area = next(area for area in bpy.context.screen.areas if area.type == 'VIEW_3D')
        space = area.spaces.active
        space.clip_start = 0.1 
        space.clip_end = 1000000.0  

        # Make a collection with the name of the imported fbx for the objects

        if bpy.data.collections.get(str(Name)):
            print(f"Collection {str(Name)} already exists, skipping...")
            return

        bpy.data.collections.new(str(Name))
        bpy.context.scene.collection.children.link(bpy.data.collections[str(Name)])
        bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[str(Name)]

        # Loop through and instance meshes
        for mesh, instances in Cfg["Instances"].items():
            if mesh not in Cfg["Parts"]:
                continue
            
            # Instance the meshes with the necessary transformations
            print(f'Instancing {mesh}')
            instance_mesh(mesh, instances)

    else:
        # Make a collection with the name of the imported fbx for the objects
        if bpy.data.collections.get(str(Name)):
            print(f"Collection {str(Name)} already exists, skipping...")
            return

        bpy.data.collections.new(str(Name))
        bpy.context.scene.collection.children.link(bpy.data.collections[str(Name)])
        bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[str(Name)]

        # Import single FBX if not a map
        mesh_file = os.path.join(f'{AssetsPath}', f'{Cfg["MeshName"]}.fbx')
        if not ImportFBX(self, mesh_file):
            return
        
        # Apply transforms if API type
        if "API" in Type or "D1API" in Type:
            for obj in GetCfgParts():
                obj.select_set(True)
                bpy.ops.object.transform_apply()

    # Assign materials if enabled
    if self.use_import_materials:
        assign_materials()
        if "API" in Type or "D1API" in Type:
            assign_gear_shader()

    if self.rename_bones or "API" in Type or "D1API" in Type:
        fix_dupe_bones()

    # Add terrain dyemaps if applicable
    if "Terrain" in Type and "TerrainDyemaps" in Cfg:
        add_terrain_dyemaps(self)

    # Final cleanup
    cleanup()

#--------------------------------------------------------------------#    
icons_dir = os.path.join(os.path.dirname(__file__), "icons")
custom_icon_col = {}

# Update variables
update_available = False
patch_notes = ""
latest_version = ""

def check_for_updates():
    global latest_version
    global patch_notes
    global current_version

    repo_name = 'DeltaDesigns/d2-map-importer-addon'
    api_url = f'https://api.github.com/repos/{repo_name}/releases/latest'
    headers = {'Accept': 'application/vnd.github.v3+json'}

    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        data = json.loads(response.text)
        latest_version = data['tag_name']
        patch_notes = data['body']
    except:
        # something went wrong with the API request, handle the error
        return

    current_version = '.'.join(map(str, bl_info["version"]))
    current_version = current_version.replace("v", "")
    latest_version = latest_version.replace("v", "")

    cur_version_parts = current_version.split(".")
    cur_version_number = int(cur_version_parts[0]) * 100 + int(cur_version_parts[1]) * 10 + int(cur_version_parts[2])

    lat_version_parts = latest_version.split(".")
    lat_version_number = int(lat_version_parts[0]) * 100 + int(lat_version_parts[1]) * 10 + int(lat_version_parts[2])

    if lat_version_number > cur_version_number:
        return True

def menu_func_import(self, context):
    self.layout.operator(ImportDestinyCfg.bl_idname, text="Destiny Importer (.cfg)", icon_value=custom_icon_col["import"]['D2ICON'].icon_id)

def register_importer():
    import bpy.utils.previews
    
    custom_icon = bpy.utils.previews.new()
    custom_icon.load("D2ICON", os.path.join(icons_dir, "destiny_icon.png"), 'IMAGE')
    custom_icon_col["import"] = custom_icon

    bpy.utils.register_class(ImportDestinyCfg)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

    global update_available 
    update_available = check_for_updates()

def unregister_importer():
    bpy.utils.previews.remove(custom_icon_col["import"])
    bpy.utils.unregister_class(ImportDestinyCfg)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

if __name__ == "__main__":
    register_importer()

    # test call
    bpy.ops.destiny.importer('INVOKE_DEFAULT')
