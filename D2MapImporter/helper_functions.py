import bpy
import D2MapImporter.destiny_importer as globals
import D2MapImporter.helper_functions as Helpers
import os
import glob
import mathutils
import json
import gc
import math

def ImportFBX(self, modelPath):
    if os.path.isfile(modelPath):
        Helpers.log(f'Importing FBX {modelPath}')
        bpy.ops.import_scene.fbx(filepath=modelPath,
                                use_anim=False,
                                use_custom_normals= not any(x in globals.Type for x in ['Decorators', 'SpeedTrees']), 
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
        Helpers.log(f"Could not find FBX: {modelPath}")
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
    for name, mesh in globals.Cfg["Parts"].items():
        # New format
        if "PartMaterials" in mesh:
            part_materials = mesh["PartMaterials"]
        else: # Old format
            part_materials = mesh
            
        for part, material in part_materials.items():
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
    Helpers.log(f"Cleaning up...")
    # if Is_Map(globals.Type):
    #     for obj in GetCfgParts():
    #         skele = obj.find_armature()
    #         if(skele):
    #             bpy.data.objects.remove(skele)
    #         bpy.data.objects.remove(obj)
    gc.collect()
    bpy.ops.outliner.orphans_purge(do_recursive = True)
    Helpers.log("Done cleaning up!")

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
        for mesh in globals.Cfg["Parts"].items():
            # New format
            if "PartMaterials" in mesh:
                part_materials = mesh["PartMaterials"]
            else: # Old format
                part_materials = mesh

            bpy.ops.object.select_all(action='DESELECT')
            #print(f"Combining meshes for '{meshes}':")

            first_obj = None  # Track the first valid object to set as active
            objects_to_join = []

            for part, material in part_materials.items():
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
        Helpers.log(f'{globals.Cfg["MeshName"]}: {error}')

def load_cfg(file_path):
    """Load and return the configuration from a file."""
    with open(file_path, 'r') as f:
        return json.load(f)

def prepare_and_process_map(self, sorted_files):
    """Prepare and process files for map import."""
    for file, size in sorted_files:
        # Skip files based on conditions
        if file.name == "":
            continue

        Helpers.log(f"File: {file.name}")
        Helpers.log(f"Name: {file.name[:-9]}")
        Helpers.log(f"Path: {globals.FilePath}")
        Helpers.log(f"Size: {size} bytes")

        # Load configuration
        globals.Cfg = load_cfg(os.path.join(globals.FilePath, file.name))
        if "ExportType" not in globals.Cfg:
            raise ImportError("You are trying to import an old cfg file. Only exports from Charm v2.5.0 or higher are supported on this version!")
        
        if "Game" in globals.Cfg:
            globals.Game = globals.TigerGame(globals.Cfg["Game"])
            Helpers.log(f"Game: {globals.Game}")
        else:
            Helpers.log("'Game' property not found in cfg file. Update your Charm or MIDA!")
            
        globals.Name = globals.Cfg["MeshName"]
        globals.Type = globals.Cfg["Type"]
        globals.ExportType = globals.Cfg["ExportType"]
        globals.AssetPath = globals.Cfg["AssetsPath"]

        if ("UnifiedAssets" in globals.Cfg) and (globals.Cfg["UnifiedAssets"] == True) and (globals.ExportType == "Map"):
            globals.AssetsPath = globals.Cfg["AssetsPath"]
        else:
            globals.AssetsPath = globals.FilePath

        Helpers.log(f"AssetsPath: {globals.AssetsPath}")

        # Prepare map import first
        globals.PrepareMapImport(self, file)

def process_instancing(self, sorted_files):
    """Process the instancing logic after importing models."""
    for file, size in sorted_files:
        # Skip files based on conditions
        if file.name == "":
            continue

        globals.Cfg = load_cfg(os.path.join(globals.FilePath, file.name))
        
        globals.Name = globals.Cfg["MeshName"]
        globals.Type = globals.Cfg["Type"]
        globals.ExportType = globals.Cfg["ExportType"]
        globals.AssetPath = globals.Cfg["AssetsPath"]

        # Handle instancing for the map or model
        globals.DoImport(self)

def instance_mesh(self, mesh, instances):
    """Handles the instancing and transformation of meshes."""
    entity_copied = False

    mesh_entry = globals.Cfg["Parts"][mesh]
    # New format
    if "PartMaterials" in mesh_entry:
        part_materials = mesh_entry["PartMaterials"]
    else: # Old format
        part_materials = mesh_entry

    for part, material in part_materials.items():
        obj = bpy.data.collections.get("Import_Temp").objects.get(part)
        if obj is None or entity_copied:
            continue

        # Handle specific type visibility settings
        if any(x in globals.Type for x in ['Decorators', 'SkyObjects', 'WaterDecals', 'RoadDecals']):
            obj.visible_shadow = False

        if(len(instances) > 10000):
            Helpers.log(f"{mesh} has {len(instances)} instances!!")

        # Creates instances
        if self.use_geo_node_instancing and any(x in globals.Type for x in ['Decorators', 'Statics']):
            Helpers.log(f"Using Geometry Node instancing for {mesh}")
            create_geometry_nodes_instancer(obj, instances)
        else:
            for i, instance in enumerate(instances):
                #Helpers.log(f'{part}: {i}/{len(instances)}')

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

def create_geometry_nodes_instancer(source_obj, instances):
    # Need to reset original obj transforms first
    quat = mathutils.Euler((0, 0, 0), 'XYZ')
    source_obj.scale = [1,1,1]
    source_obj.rotation_mode = 'XYZ'
    source_obj.rotation_euler = quat

    name = source_obj.name
    positions = [inst["Translation"] for inst in instances]
    mesh = bpy.data.meshes.new(name + "_Points")
    mesh.from_pydata(positions, [], [])
    mesh.update()
  
    rot_attr = mesh.attributes.new(
        name="instance_rotation",
        type='FLOAT_VECTOR',
        domain='POINT'
    )

    scale_attr = mesh.attributes.new(
        name="instance_scale",
        type='FLOAT_VECTOR',
        domain='POINT'
    )

    for i, inst in enumerate(instances):
        quat = mathutils.Quaternion([inst["Rotation"][3], inst["Rotation"][0], inst["Rotation"][1], inst["Rotation"][2]])
        euler = quat.to_euler("XYZ")
        rot_attr.data[i].vector = euler
        scale_attr.data[i].vector = inst["Scale"]

    points_obj = bpy.data.objects.new(name + "_PointsObj", mesh)
    points_obj.data.materials.append(source_obj.data.materials[0])
    bpy.context.collection.objects.link(points_obj)

    # camera culling setup only works on blender 5.0+, and should only be used for decorators
    if bpy.app.version < (5, 0, 0) or any(x in globals.Type for x in ['Statics']):
        create_geometry_nodes_instancer_blender4(mesh, points_obj, source_obj, instances)
    else:
        node_group = bpy.data.node_groups.get("InstancerGeoNodes")
        if node_group is None:
            addon_dir = os.path.dirname(__file__)
            full_path = os.path.join(addon_dir, "blends/Instancer.blend")
            with bpy.data.libraries.load(full_path) as (data_from, data_to):
                data_to.node_groups = ["InstancerGeoNodes"]
            bpy.data.node_groups.get(f"InstancerGeoNodes").use_fake_user = True
            node_group = bpy.data.node_groups.get("InstancerGeoNodes")

        unique_group = node_group.copy()
        unique_group.name = f"Instancer_{name}"

        modifier = points_obj.modifiers.new("GeometryNodes", "NODES")
        modifier.node_group = unique_group

        nodes = unique_group.nodes
        instancer = nodes.get("Instancer")
        instancer.inputs["Object"].default_value = source_obj

def create_geometry_nodes_instancer_blender4(mesh, points_obj, source_obj, instances):
    name = source_obj.name
    modifier = points_obj.modifiers.new("GeometryNodes", "NODES")
    node_group = bpy.data.node_groups.new(name + "_NodeTree", "GeometryNodeTree")
    modifier.node_group = node_group

    nodes = node_group.nodes
    links = node_group.links
    nodes.clear()

    node_group.interface.new_socket(
        name="Geometry",
        in_out='INPUT',
        socket_type="NodeSocketGeometry"
    )

    node_group.interface.new_socket(
        name="Geometry",
        in_out='OUTPUT',
        socket_type="NodeSocketGeometry"
    )

    node_group.interface_update(bpy.context)

    group_input = nodes.new("NodeGroupInput")
    group_output = nodes.new("NodeGroupOutput")

    instance_on_points = nodes.new("GeometryNodeInstanceOnPoints")
    object_info = nodes.new("GeometryNodeObjectInfo")

    rot_attr_node = nodes.new("GeometryNodeInputNamedAttribute")
    rot_attr_node.data_type = 'FLOAT_VECTOR'
    rot_attr_node.inputs["Name"].default_value = "instance_rotation"

    scale_attr_node = nodes.new("GeometryNodeInputNamedAttribute")
    scale_attr_node.data_type = 'FLOAT_VECTOR'
    scale_attr_node.inputs["Name"].default_value = "instance_scale"

    object_info.inputs["Object"].default_value = source_obj
    object_info.transform_space = 'RELATIVE'

    links.new(group_input.outputs["Geometry"], instance_on_points.inputs["Points"])
    links.new(object_info.outputs["Geometry"], instance_on_points.inputs["Instance"])
    links.new(rot_attr_node.outputs["Attribute"], instance_on_points.inputs["Rotation"])
    links.new(scale_attr_node.outputs["Attribute"], instance_on_points.inputs["Scale"])
    links.new(instance_on_points.outputs["Instances"], group_output.inputs["Geometry"])

    return points_obj

def store_split_normals_attribute(
    object=None,
	attr_name="raw_vertex_norm",
    flag_attr_name="has_raw_norm"):

    if object is None:
        log("No object passed? This shouldn't happen.")
        return

    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    mesh = object.data
    if attr_name in mesh.attributes:
        attr = mesh.attributes[attr_name]
    else:
        attr = mesh.attributes.new(
            name=attr_name,
            type='FLOAT_VECTOR',
            domain='CORNER'
        )

    if flag_attr_name in mesh.attributes:
        flag_attr = mesh.attributes[flag_attr_name]
    else:
        flag_attr = mesh.attributes.new(
            name=flag_attr_name,
            type='FLOAT_VECTOR',
            domain='CORNER'
        )

    for i, loop in enumerate(mesh.loops):
        attr.data[i].vector = loop.normal
        flag_attr.data[i].vector = (1,1,1)

def store_vertex_positions_attribute(
    object=None,
    attr_name="raw_vertex_pos",
    flag_attr_name="has_raw_pos"):

    if object is None:
        log("No object passed? This shouldn't happen.")
        return

    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    mesh = object.data
    if attr_name in mesh.attributes:
        attr = mesh.attributes[attr_name]
    else:
        attr = mesh.attributes.new(
            name=attr_name,
            type='FLOAT_VECTOR',
            domain='POINT'
        )

    if flag_attr_name in mesh.attributes:
        flag_attr = mesh.attributes[flag_attr_name]
    else:
        flag_attr = mesh.attributes.new(
            name=flag_attr_name,
            type='FLOAT_VECTOR',
            domain='POINT'
        )

    for i, vert in enumerate(mesh.vertices):
        attr.data[i].vector = vert.co
        flag_attr.data[i].vector = (1,1,1)

def log(string):
    print(f"[Tiger Importer]: {string}")

def fnv1_32(data: str) -> int:
    FNV_PRIME = 0x01000193
    OFFSET_BASIS = 0x811C9DC5

    hash_ = OFFSET_BASIS
    for b in data.encode("utf-8"):
        hash_ = (hash_ * FNV_PRIME) & 0xffffffff
        hash_ ^= b
    return hash_
               