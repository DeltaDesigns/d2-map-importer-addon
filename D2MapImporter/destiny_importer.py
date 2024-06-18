from .__init__ import bl_info
import bpy
from bpy.props import *
import json
import mathutils
import os
import math
import requests
import json

from .helper_functions import *
from .materials import *
from .lights import *
from .api import *

# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty, CollectionProperty, FloatProperty
from bpy.types import Operator

from multiprocessing import Process, cpu_count

# Globals for cfg related stuff
Cfg = None
FilePath = None
Name = None
Type = "Map" #Default to map

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

    merge_meshes: BoolProperty(
            name="Combine Meshes",
            description="Combine all parts of a model into one mesh.\nWill slow down import (drastically on large maps) but can increase performace slightly",
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

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.label(text="Current Version: " + current_version)
        box.label(text="Options:")
        box.prop(self, 'merge_meshes')
        box.prop(self, 'use_import_materials')
        box.prop(self, 'import_lights')
        box.prop(self, 'light_intensity_override')
        box.prop(self, 'override_light_color')

        box2 = layout.box()
        box2.label(text="Misc:")
        box2.prop(self, 'use_terrain_dyemap_output')
        box2.prop(self, 'import_dyn_points')
        
        if update_available:
            box = layout.box()
            box.label(text="Update available: " + latest_version)
            box.operator("wm.url_open", text="Get Latest Release").url = "https://github.com/DeltaDesigns/d2-map-importer-addon/releases/latest"

    def execute(self, context):
        # Deselect all objects just in case
        bpy.ops.object.select_all(action='DESELECT')

        if self.files:
            #ShowMessageBox(f"Importing...", "This might take some time! (Especially on multiple imports)", 'ERROR')
            dirname = os.path.dirname(self.filepath)
            
            # Create a list of (file, size) tuples and sort by size
            file_sizes = [(file, os.path.getsize(os.path.join(dirname, file.name))) for file in self.files]
            sorted_files = sorted(file_sizes, key=lambda x: x[1], reverse=True)

            global FilePath
            for file, size in sorted_files:
                if(('EntityPoints' in file.name) and not self.import_dyn_points):
                    continue
                FilePath = dirname           
                print(f"File: {file.name}")
                print(f"Name: {file.name[:-9]}")
                print(f"Path: {FilePath}")
                print(f"Size: {size} bytes")
                ReadCFG(self, file)

        return {'FINISHED'} # Lets Blender know the operator finished successfully.

# Where all the fun happens..

def ReadCFG(self, file):
    global Cfg, Name, Type

    with open(FilePath + f"\\{file.name}", 'r') as f:
        Cfg = json.load(f)
    
    Name = Cfg["MeshName"]
    if "Type" in Cfg:
        Type = Cfg["Type"]

    print(f"Starting import on {Type}: {Name}")

    ImportFBX(self)

def ImportFBX(self):
    # Check if the file exists
    if os.path.isfile(FilePath+ "\\" + Name + ".fbx"):
        # Make a collection with the name of the imported fbx for the objects
        bpy.data.collections.new(str(Name))
        bpy.context.scene.collection.children.link(bpy.data.collections[str(Name)])
        bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[str(Name)]

        bpy.ops.import_scene.fbx(filepath=FilePath+ "\\" + Name + ".fbx", use_custom_normals=True, ignore_leaf_bones=False, automatic_bone_orientation=True)# force_connect_children=True)
        add_to_collection(Name) 
    else:
        print(f"Could not find FBX: {Name}")
        # If theres no fbx and no decals or lights in the cfg, skip the import
        if len(Cfg["Decals"]) == 0 and len(Cfg["Lights"]) == 0:
            return
    
    # Merge meshes, create instances for maps only
    if Is_Map(Type):
        if self.merge_meshes: 
           CombineMeshes()
            
        # Loops through "Instances" in the Cfg and creates the instances with their transforms
        for mesh, instances in Cfg["Instances"].items():
            if mesh not in Cfg["Parts"]:
                continue

            # Kind of a hacky fix but this stops entities with skeletons from being copied more times than they should
            entityCopied = False
            for part, material in Cfg["Parts"][mesh].items():
                obj = bpy.data.objects.get(part)
                if obj is None or entityCopied:
                    continue
                
                if 'Decorators' in globals.Cfg["MeshName"] or 'SkyEnts' in globals.Cfg["MeshName"]:
                    obj.visible_shadow = False

                for i, instance in enumerate(instances):
                    # Creates instance
                    original_armature = bpy.data.objects[part].find_armature()
                    if original_armature: # For dynamics with skeletons, need to copy the skeleton and meshes THEN reparent the copied meshes to the copied skeleton and change its armature modifier...
                        obj = duplicate_armature_with_children(original_armature)
                        entityCopied = True
                    else: 
                        obj = obj.copy()
                        bpy.context.collection.objects.link(obj)

                    # Get instance transforms
                    location = instance["Translation"]
                    scale = instance["Scale"]
                    if isinstance(scale, float):  # Compatibility for older Charm versions
                        scale = [scale] * 3
                    # WXYZ
                    quat = mathutils.Quaternion([instance["Rotation"][3], instance["Rotation"][0], instance["Rotation"][1], instance["Rotation"][2]])

                    # Set transforms
                    obj.location = location
                    obj.rotation_mode = 'QUATERNION'
                    obj.rotation_quaternion = quat
                    obj.scale = scale
    else:
        # Clear all transforms, because everything imports tiny and rotated on its side for some reason
        for obj in GetCfgParts():
            obj.select_set(True)
            bpy.ops.object.rotation_clear(clear_delta=False)
            bpy.ops.object.scale_clear(clear_delta=False)

    if self.use_import_materials:
        assign_materials()
        if "API" in Type:
            assign_gear_shader()

    if self.import_lights:
        add_lights(self)

    if "Terrain" in Type:
        if "TerrainDyemaps" in Cfg:
            add_terrain_dyemaps(self)
        # for obj in GetCfgParts():
        #     obj.select_set(True)
        #     bpy.ops.object.rotation_clear(clear_delta=False)

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
