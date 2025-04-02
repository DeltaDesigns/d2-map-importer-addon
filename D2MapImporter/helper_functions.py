import bpy
import D2MapImporter.destiny_importer as globals
import os
import glob
import mathutils
import json
import gc

def ImportFBX(self, modelPath):
    if os.path.isfile(modelPath):
        print(f'Importing FBX {modelPath}')
        bpy.ops.import_scene.fbx(filepath=modelPath,
                                use_anim=False,
                                use_custom_normals=True, 
                                ignore_leaf_bones=False, 
                                automatic_bone_orientation=True,
                                global_scale=100.0, 
                                use_image_search = False,
                                use_manual_orientation=True, 
                                axis_up='Z', 
                                axis_forward='-X')# force_connect_children=True)
        
        #add_to_collection(globals.Name) 
        return True
    else:
        print(f"Could not find FBX: {modelPath}")
        return False

def ShowMessageBox(message = "", title = "Message Box", icon = 'INFO'):
    def draw(self, context):
        self.layout.label(text=message)
    bpy.context.window_manager.popup_menu(draw, title = title, icon = icon)

def Is_Map(ExportType):
    return "Map" in ExportType

def add_to_collection(name):
    # List of object references
    objs = GetCfgParts()
    # Set target collection to a known collection 
    coll_target = bpy.context.scene.collection.children.get(str(name))
    # If target found and object list not empty
    if coll_target and objs:
        # Loop through all objects
        for ob in objs:
            # Loop through all collections the obj is linked to
            for coll in ob.users_collection:
                # Unlink the object
                coll.objects.unlink(ob)
            # Link each object to the target collection
            coll_target.objects.link(ob)

def GetCfgParts():
    Parts = [] 
    for meshes, mesh in globals.Cfg["Parts"].items():
        for part, material in mesh.items():
            obj = bpy.data.objects.get(part)
            if not obj:
                continue 
            Parts.append(obj)
    return Parts

def GetTexture(image_name):
    # List of common image extensions
    image_extensions = ['*.dds', '*.tga', '*.jpg', '*.jpeg', '*.png', '*.bmp', '*.gif', '*.tiff', '*.webp']

    # Iterate through extensions and search for matching files
    for extension in image_extensions:
        pattern = os.path.join(globals.AssetsPath, f"Textures/{image_name}{extension[1:]}")  # Remove '*' from extension
        files = glob.glob(pattern)
        if files:  # If any files are found, return the first one
            if bpy.data.images.get(os.path.basename(files[0])) is None:
                bpy.data.images.load(files[0], check_existing = True)
                #print(f'Loaded {os.path.basename(files[0])}')

            img = os.path.basename(files[0])
            return img
    return None

def cleanup():
    print(f"Cleaning up...")
    # if Is_Map(globals.Type):
    #     for obj in GetCfgParts():
    #         skele = obj.find_armature()
    #         if(skele):
    #             bpy.data.objects.remove(skele)
    #         bpy.data.objects.remove(obj)
    gc.collect()
    bpy.ops.outliner.orphans_purge(do_recursive = True)
    print("Done cleaning up!")

def duplicate_armature_with_children(armature):
    new_armature = armature.copy()
    # Loop through the children of the parent object
    for child in armature.children:
        # Create a copy of the child object
        new_child = child.copy()
        # Add the copy to the scene
        bpy.context.scene.collection.objects.link(new_child)
        # Parent the new child to the new parent
        new_child.parent = new_armature
        # Loop through the child's modifiers
        for modifier in new_child.modifiers:
            # Check if the modifier is an armature modifier
            if modifier.type == 'ARMATURE':
                # Set the armature object in the modifier to the new armature
                modifier.object = new_armature

        for collection in new_child.users_collection: #...
            # Unlink the armature from the collection
            collection.objects.unlink(new_child)
            
        bpy.context.view_layer.active_layer_collection.collection.objects.link(new_child) #add the child to the collection (again, idk why this is needed)
    # Move the new armature to the new collection
    bpy.context.view_layer.active_layer_collection.collection.objects.link(new_armature)

    return new_armature

def CombineMeshes():
    try:
        for meshes, mesh in globals.Cfg["Parts"].items():
            bpy.ops.object.select_all(action='DESELECT')
            print(f"Combining meshes for '{meshes}':")

            first_obj = None  # Track the first valid object to set as active
            objects_to_join = []

            for part, material in mesh.items():
                obj = bpy.data.objects.get(part)
                if not obj:
                    continue
                objects_to_join.append(obj)
                if first_obj is None:
                    first_obj = obj

            # Ensure there's at least one object to join
            if not first_obj or len(objects_to_join) < 2:
                continue

            # Set the first object as active
            bpy.context.view_layer.objects.active = first_obj

            # Select all objects for joining
            for obj in objects_to_join:
                obj.select_set(True)

            # Ensure we're in Object mode before joining
            bpy.ops.object.mode_set(mode='OBJECT')

            # Perform the join operation
            bpy.ops.object.join()

            # Deselect all after joining
            bpy.ops.object.select_all(action='DESELECT')
    except Exception as error:
        print(f'{globals.Cfg["MeshName"]}: {error}')

def load_cfg(file_path):
    """Load and return the configuration from a file."""
    with open(file_path, 'r') as f:
        return json.load(f)

def prepare_and_process_map(self, sorted_files):
    """Prepare and process files for map import."""
    for file, size in sorted_files:
        # Skip files based on conditions
        if 'EntityPoints' in file.name and not self.import_dyn_points or file.name == "":
            continue

        print(f"File: {file.name}")
        print(f"Name: {file.name[:-9]}")
        print(f"Path: {globals.FilePath}")
        print(f"Size: {size} bytes")

        # Load configuration
        globals.Cfg = load_cfg(globals.FilePath + f"\\{file.name}")
        if "ExportType" not in globals.Cfg:
            raise ImportError("You are trying to import an old cfg file. Only exports from Charm v2.5.0 or higher are supported on this version!")
        
        globals.Name = globals.Cfg["MeshName"]
        globals.Type = globals.Cfg["Type"]
        globals.ExportType = globals.Cfg["ExportType"]
        globals.AssetsPath = globals.Cfg["AssetsPath"]
        print(f"AssetsPath: {globals.AssetsPath}")

        # Prepare map import first
        globals.PrepareMapImport(self, file)

def process_instancing(self, sorted_files):
    """Process the instancing logic after importing models."""
    for file, size in sorted_files:
        # Skip files based on conditions
        if 'EntityPoints' in file.name and not self.import_dyn_points or file.name == "":
            continue

        # Load configuration
        globals.Cfg = load_cfg(globals.FilePath + f"\\{file.name}")
        
        globals.Name = globals.Cfg["MeshName"]
        globals.Type = globals.Cfg["Type"]
        globals.ExportType = globals.Cfg["ExportType"]
        globals.AssetPath = globals.Cfg["AssetsPath"]

        # Handle instancing for the map or model
        globals.DoImport(self)

def instance_mesh(mesh, instances):
    """Handles the instancing and transformation of meshes."""
    entity_copied = False
    for part, material in globals.Cfg["Parts"][mesh].items(): 
        #obj = bpy.data.objects.get(part)
        obj = bpy.data.collections.get("Import_Temp").objects.get(part)
        if obj is None or entity_copied:
            continue

        # Handle specific type visibility settings
        if any(x in globals.Type for x in ['Decorators', 'SkyObjects', 'WaterDecals', 'RoadDecals']):
            obj.visible_shadow = False

        # Creates instances
        for i, instance in enumerate(instances):
            # Handle armature duplication for skeleton-based meshes
            armature = bpy.data.objects[part].find_armature()
            if armature:
                obj = armature 

            if armature:
                obj = duplicate_armature_with_children(armature)
                entity_copied = True
            else:
                obj = obj.copy()
                bpy.context.collection.objects.link(obj)

            # Set instance transforms
            location = instance["Translation"]
            scale = instance["Scale"]
            quat = mathutils.Quaternion([instance["Rotation"][3], instance["Rotation"][0], instance["Rotation"][1], instance["Rotation"][2]])
            if globals.Type == "Terrain":
                quat = mathutils.Quaternion([1,0,0,0])

            obj.location = location
            obj.rotation_mode = 'QUATERNION'
            obj.rotation_quaternion = quat
            obj.scale = scale

            #if i != len(instances) - 1:  # Don't copy if this was the last instance
               