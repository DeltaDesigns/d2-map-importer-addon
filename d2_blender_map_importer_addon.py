import bpy
from bpy.props import *
import json
import mathutils
import os
import math
import requests
import json

bl_info = {
    "name": "Destiny 2 Importer",
    "author": "DeltaDesigns, Montague/Monteven",
    "version": (0, 6, 2),
    "blender": (3, 0, 0),
    "location": "File > Import",
    "description": "Import Destiny 2 Maps/Objects exported from Charm",
    "warning": "BETA",
    "category": "Import",
    "package": "d2_map_importer"
    }

# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty, CollectionProperty, FloatProperty
from bpy.types import Operator

icons_dir = os.path.join(os.path.dirname(__file__), "icons")
custom_icon_col = {}

#Update variables
update_available = False
patch_notes = ""
latest_version = ""

class ImportD2Map(Operator, ImportHelper):
    bl_idname = "d2map.import"        # Unique identifier for buttons and menu items to reference.
    bl_label = "Import .cfg"         # Display name in the interface.
    bl_options = {'UNDO', 'PRESET'}
    
    @classmethod
    def poll(self, context):
        return context.mode == 'OBJECT'

    #.cfg specific variables
    config = None
    FilePath = None
    Name = None
    type = "Map" #Default to map

    static_names = {} #original static objects

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

    combine_statics: BoolProperty(
            name="Combine Static Meshes",
            description="Combine all parts of a model into one mesh\nWill slow down import but will increase performace",
            default=True,
            )

    use_import_materials: BoolProperty(
            name="Import Textures",
            description="Imports textures and tries to apply them to the models\nTextures folder must be in the same place as the .cfg you are importing",
            default=True,
            )
    
    import_lights: BoolProperty(
            name="Import Lights",
            description="Imports basic Point Lights\nSome light colors can/will be wrong\nIntensity is the same for all",
            default=True,
            )
    
    light_intensity_override: FloatProperty(
        name="Light Intensity",
        description="Imported light intensity",
        default=200.0,  # Default value
        min=0.0,      # Minimum value
        soft_max=10000.0,  # Maximum value
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

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.label(text="Current Version: " + current_version)
        box.label(text="Options:")
        box.prop(self, 'combine_statics')
        box.prop(self, 'use_import_materials')
        box.prop(self, 'import_lights')
        box.prop(self, 'light_intensity_override')
        box.prop(self, 'override_light_color')

        box2 = layout.box()
        box2.label(text="Misc:")
        box2.prop(self, 'use_terrain_dyemap_output')
        
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

            for file, size in sorted_files:
                self.Filepath = dirname           
                print(f"File: {file.name}")
                print(f"Name: {file.name[:-9]}")
                print(f"Path: {self.Filepath}")
                print(f"Size: {size} bytes")

                import_cfg(self, file, self.Filepath)

        return {'FINISHED'} # Lets Blender know the operator finished successfully.

#Where all the fun happens..

def import_cfg(self, file, Filepath):
    self.static_names = {}

    Name = file.name[:-9] #Removes the _info.cfg from the name
    
    self.config = json.load(open(Filepath + f"\\{file.name}"))
    
    if "Type" in self.config:
        self.type = self.config["Type"]

    print(f"Starting import on {self.type}: {Name}")
   
    # for name, data in self.config["Decals"].items():
    #     for corner in data: 
    #         createprojectionbox(name, (mathutils.Vector((corner["Corner1"][0],corner["Corner1"][1],corner["Corner1"][2]))), mathutils.Vector((corner["Corner2"][0],corner["Corner2"][1],corner["Corner2"][2])), corner["Material"])
    
    # assign_materials(self)
    # return

    #make a collection with the name of the imported fbx for the objects
    bpy.data.collections.new(str(Name))
    bpy.context.scene.collection.children.link(bpy.data.collections[str(Name)])
    bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[str(Name)]

    # Check if the file exists
    if os.path.isfile(Filepath+ "\\" + Name + ".fbx"):
        bpy.ops.import_scene.fbx(filepath=Filepath+ "\\" + Name + ".fbx", use_custom_normals=True, ignore_leaf_bones=False, automatic_bone_orientation=True)# force_connect_children=True)
    else:
        print(f"Could not find FBX: {Name}")
        return
    
    add_to_collection(self) 

    newobjects = bpy.data.collections[str(Name)].objects

    #Merge statics, create instances for maps only
    if Is_Map(self):
        if self.combine_statics: #and not "Dynamics" in self.type:
            # Get selected objects after import
            selected_objects = bpy.context.selected_objects
            # Dictionary to store imported objects
            imported_objects = {}
            # Add selected objects to the dictionary
            imported_objects[Name] = selected_objects

            # Combine objects with the same prefix and join their meshes
            for Name, objects in imported_objects.items():
                combined_objects = {}  # To store combined meshes

                for obj in objects:
                    if obj.type == 'MESH':
                        prefix = obj.name[:8]  # Get the first 8 characters of the object name

                        if prefix not in combined_objects:
                            combined_objects[prefix] = []

                        combined_objects[prefix].append(obj)

                # Join meshes with the same prefix
                for prefix, obj_list in combined_objects.items():
                    if len(obj_list) > 1:
                        print(f"Combining meshes for '{prefix}':")
                        bpy.context.view_layer.objects.active = obj_list[0]  # Set the active object for joining
                        bpy.ops.object.select_all(action='DESELECT')

                        for obj in obj_list:
                            #print(f"  {obj.name}")
                            obj.select_set(True)

                        bpy.ops.object.join()

            # Clear selection
            bpy.ops.object.select_all(action='DESELECT')
            bpy.ops.outliner.orphans_purge()

        newobjects = [] #Clears the list just in case
        newobjects = bpy.data.collections[str(Name)].objects #Readds the objects in the collection to the list

        for x in newobjects:
            if x.type != 'EMPTY':
                if len(self.config["Parts"].items()) <= 1: #Fix for error that occurs when theres only 1 object in the fbx
                    for newname, value in self.config["Parts"].items():
                        x.name = newname[:8]

                obj_name = x.name[:8]
                if obj_name not in self.static_names.keys():
                    self.static_names[obj_name] = []
                self.static_names[obj_name].append(x.name)
                #print(f"Added {x.name} to static_names")

        print("Instancing...")

        for static, instances in self.config["Instances"].items():
            try:  # fix this
                parts = self.static_names[static[:8]]
            except:
                print(f"Failed on {static}. FBX may contain only 1 object")
                continue

            for part in parts:
                for instance in instances:
                    original_armature = bpy.data.objects[part].find_armature()
                    if original_armature: #For dynamics with skeletons, need to copy the skeleton and meshes THEN reparent the copied meshes to the copied skeleton and change its armature modifier...
                        ob_copy = original_armature.copy()
                        print(f"Object '{bpy.data.objects[part].name}' is parented to an armature '{ob_copy.name}'")
                        
                        # Loop through the children of the parent object
                        for child in bpy.data.objects[part].parent.children:
                            # Create a copy of the child object
                            new_child = child.copy()
                            # Add the copy to the scene
                            bpy.context.scene.collection.objects.link(new_child)
                            # Parent the new child to the new parent
                            new_child.parent = ob_copy
                            # Loop through the child's modifiers
                            for modifier in new_child.modifiers:
                                # Check if the modifier is an armature modifier
                                if modifier.type == 'ARMATURE':
                                    # Set the armature object in the modifier to the new armature
                                    modifier.object = ob_copy

                            for collection in new_child.users_collection: #...
                                # Unlink the armature from the collection
                                collection.objects.unlink(new_child)
                                
                            bpy.context.view_layer.active_layer_collection.collection.objects.link(new_child) #add the child to the collection (again, idk why this is needed)
                        # Move the new armature to the new collection
                        bpy.context.view_layer.active_layer_collection.collection.objects.link(ob_copy)
                    else:
                        ob_copy = bpy.data.objects[part].copy()
                        bpy.context.collection.objects.link(ob_copy) #makes the instances

                    location = [instance["Translation"][0], instance["Translation"][1], instance["Translation"][2]]
                    if type(instance["Scale"]) == float: #Compatibility for older charm verisons
                        scale = [instance["Scale"]]*3
                    else:
                        scale = [instance["Scale"][0], instance["Scale"][1], instance["Scale"][2]]
                    #Reminder that blender uses WXYZ, the order in the confing file is XYZW, so W is always first
                    quat = mathutils.Quaternion([instance["Rotation"][3], instance["Rotation"][0], instance["Rotation"][1], instance["Rotation"][2]])

                    ob_copy.location = location
                    ob_copy.rotation_mode = 'QUATERNION'
                    ob_copy.rotation_quaternion = quat
                    ob_copy.scale = scale
    
    if not Is_Map(self):
        for x in newobjects:
            if len(self.config["Parts"].items()) <= 1: #Fix for error that occurs when theres only 1 object in the fbx
                for newname, value in self.config["Parts"].items():
                    x.name = newname
        # if "Entity" in self.type:
        #     fix_dup_bones(self, newobjects)

        for x in newobjects:
            x.select_set(True)
            #Clear the scale and rotation of the entity
            bpy.ops.object.rotation_clear(clear_delta=False)
            bpy.ops.object.scale_clear(clear_delta=False)

    if self.use_import_materials:
        assign_materials(self)
        if "API" in self.type:
            assign_gear_shader(self, newobjects, Filepath)

    if "Terrain" in self.type:
        if "TerrainDyemaps" in self.config:
            add_terrain_dyemaps(self, newobjects)
        for x in newobjects:
            x.select_set(True)
            bpy.ops.object.rotation_clear(clear_delta=False) #Clears the rotation of the terrain

        #Import Lights, testing
    if self.import_lights:
        add_lights(self)
                    
    cleanup(self)
    print(f"Finished Importing {self.type}: {Name}")

def add_lights(self):
    if "Lights" in self.config:
        for name, lights in self.config["Lights"].items():
            for data in lights: 
                if bpy.data.lights.get(data["Type"] + f"_{name}") is None:
                    # Create a new point light
                    light_data = bpy.data.lights.new(name=data["Type"] + f"_{name}", type=data["Type"].upper())
                    light_object = bpy.data.objects.new(name=data["Type"] + f"_{name}", object_data=light_data)
                    bpy.context.collection.objects.link(light_object)

                    # Check if the selected object is an Area light
                    if light_object.data.type == 'AREA':
                        # Change the shape and size of the light
                        light_object.data.shape = 'RECTANGLE'  # Set the shape to rectangle

                        # Set the size of the light
                        light_object.data.size = data["Size"][0]/2  # Set the width to 2.0 units
                        light_object.data.size_y = data["Size"][1]/2 # Set the height to 1.0 unit

                    # Set the light's color
                    color = data["Color"]
                    if data["Color"] == [0,0,0] and self.override_light_color:
                        color = [1,1,1]
                    light_object.data.color = color  # RGB values ranging from 0.0 to 1.0
                    light_object.data.energy = self.light_intensity_override

                    # Set the light to be visible in the viewport and in renders
                    light_object.hide_viewport = False
                    light_object.hide_render = False

                    location = [data["Translation"][0], data["Translation"][1], data["Translation"][2]]
                    # Reminder that Blender uses WXYZ, the order in the config file is XYZW, so W is always first
                    quat = mathutils.Quaternion([data["Rotation"][3], data["Rotation"][0], data["Rotation"][1], data["Rotation"][2]])

                    light_object.location = location
                    light_object.rotation_mode = 'QUATERNION'
                    light_object.rotation_quaternion = quat
                else:
                    light_object = bpy.data.objects.get(data["Type"] + f"_{name}").copy()
                    bpy.context.collection.objects.link(light_object) #makes the instances

                    location = [data["Translation"][0], data["Translation"][1], data["Translation"][2]]
                    # Reminder that Blender uses WXYZ, the order in the config file is XYZW, so W is always first
                    quat = mathutils.Quaternion([data["Rotation"][3], data["Rotation"][0], data["Rotation"][1], data["Rotation"][2]])

                    light_object.location = location
                    light_object.rotation_mode = 'QUATERNION'
                    light_object.rotation_quaternion = quat

def assign_materials(self):
    print("Assigning materials...")
    global image_extension
    materials = bpy.data.materials
    for k in materials: #Removes the last _ and anything after it in the material name, so the name matches the config files
        if k.name.count("_") > 1:
            k.name = k.name[:k.name.rfind("_")]

    for staticname, matname in self.config["Parts"].items(): #Renames the materials to the actual material hash in the config file
        for mats in materials:
            if mats.name == staticname:
                mats.name = matname
            else:
                if len(self.config["Parts"].items()) <= 1:
                    for name, mat in self.config["Parts"].items():
                        if bpy.data.objects[name[:8]].type == 'MESH':
                            bpy.data.objects[name[:8]].active_material.name = mat

    for obj in bpy.data.objects: #remove any duplicate materials that may have been created
        if obj.type == 'MESH':
            for slt in obj.material_slots:
                part = slt.name.rpartition('.')
                if part[2].isnumeric() and part[0] in materials:
                    slt.material = materials.get(part[0])
        
    #Get all the images in the directory and load them
    #Should probably change this to only load the textures included in the cfg, as to not load unneeded textures
    for img in os.listdir(self.Filepath + "/Textures/"):
        if img.endswith(".png") or img.endswith(".tga"):
            bpy.data.images.load(self.Filepath + "/Textures/" + f"/{img}", check_existing = True)
            if img.endswith(".png"):
                image_extension = ".png"
            if img.endswith(".tga"):
                image_extension = ".tga"
            print(f"Loaded {img}")
    
    d = {x : y["PS"] for x, y in self.config["Materials"].items()}
    for k, mat in d.items():
        try:
            matnodes = bpy.data.materials[k].node_tree.nodes
            if matnodes.find('Principled BSDF') != -1:
                matnodes['Principled BSDF'].inputs['Metallic'].default_value = 0 

            #To make sure the current material already doesnt have at least one texture node
            if not len(find_nodes_by_type(bpy.data.materials[k], 'TEX_IMAGE')) > 0: #
                tex_num = 0 #To keep track of the current position in the list
                for n, info in mat.items():
                    current_image = info["Hash"] + image_extension

                    if info["SRGB"]:
                        colorspace = "sRGB"
                    else: 
                        colorspace = "Non-Color"

                    texnode = matnodes.new('ShaderNodeTexImage')
                    texnode.hide = True
                    texnode.location = (-370.0, 200.0 + (float(tex_num)*-1.1)*50) #shitty offsetting

                    texture = bpy.data.images.get(current_image)
                    if texture:
                        texnode.label = texture.name
                        texture.colorspace_settings.name = colorspace
                        texture.alpha_mode = "CHANNEL_PACKED"
                        texnode.image = texture      #Assign the texture to the node

                        #assign the first texture to material's diffuse just to help a little, good luck o7
                        link_diffuse(bpy.data.materials[k])

                        # if texture.colorspace_settings.name == "sRGB":     
                        #     link_diffuse(bpy.data.materials[k])
                        # if texture.colorspace_settings.name == "Non-Color":
                        #     if int(tex_num) == 0:
                        #         link_diffuse(bpy.data.materials[k])
                        #     else:
                        #         link_normal(bpy.data.materials[k], int(tex_num))
                    tex_num += 1
        except KeyError:
            print("Material not found: ", k)

#THIS CODE SUCKS BUT IT WORKS SO I DONT CARE ANYMORE
def add_terrain_dyemaps(self, objects):
    for obj in objects:
        prefix = obj.name[:8]
        
        for slot in obj.material_slots:
            material = slot.material
            if len(material.name) > 8: #ugh
               continue
            
            if material:
                if bpy.data.materials.get(f"{prefix}_{material.name}") is not None:
                    slot.material = bpy.data.materials[f"{prefix}_{material.name}"]
                else:
                    #Copy and rename the material
                    material_copy = material.copy()
                    material_copy.name = f"{prefix}_{material.name}"
                    slot.material = material_copy

                    #Add the dyemap textures
                    tex_num = 1 #To keep track of the current position in the list
                    matnodes = bpy.data.materials[material_copy.name].node_tree.nodes

                    if bpy.data.node_groups.get("Dyemap Converter") is None:
                        #Gets the terrain nodegroup from the addon directory
                        addon_dir = os.path.dirname(__file__)
                        full_path = os.path.join(addon_dir, "D2MapImporter/D2TerrainNode.blend")

                        # Load the node group
                        with bpy.data.libraries.load(full_path) as (data_from, data_to):
                            data_to.node_groups = ["Dyemap Converter"]

                    # Check if the node group was loaded successfully
                    if "Dyemap Converter" in bpy.data.node_groups:
                        # Create a new node for the loaded node group
                        terrain_node = matnodes.new(type='ShaderNodeGroup')
                        terrain_node.name = "Dyemap Converter"
                        terrain_node.location = (20.0, 1200.0)  # Set the location of the node
                        terrain_node.node_tree = bpy.data.node_groups["Dyemap Converter"]
                    else:
                        print(f"Failed to load node group.")

                    frame_node = matnodes.new(type='NodeFrame')
                    frame_node.label = "Terrain Dyemaps"
                    try:
                        # Get the total number of inputs in the node
                        num_inputs = 16  # Total number of inputs in the node
                        num_textures = len(self.config["TerrainDyemaps"][prefix])

                        # Calculate the starting index for texture assignment
                        start_index = num_inputs - num_textures

                        # Iterate through the textures and assign them to the node inputs
                        for i, tex in enumerate(self.config["TerrainDyemaps"][prefix]):
                            input_index = (start_index + i + 1) % (num_inputs + 1)  # Adjusted for 1-based indexing

                            texnode = matnodes.new('ShaderNodeTexImage')
                            texnode.hide = True
                            texnode.location = (-360.0, 1200.0 + (float(tex_num) * -1.1) * 50)  # Shitty offsetting

                            texture = bpy.data.images.get(tex + image_extension)
                            if texture:
                                texnode.label = texture.name
                                texture.colorspace_settings.name = "Non-Color"
                                texnode.extension = 'EXTEND'
                                texture.alpha_mode = "CHANNEL_PACKED"
                                texnode.image = texture  # Assign the texture to the node
                                texnode.parent = frame_node

                            try:
                                material_copy.node_tree.links.new(terrain_node.inputs[f'Dyemap {input_index}'], texnode.outputs[0])
                                material_copy.node_tree.links.new(terrain_node.inputs[f'Dyemap {input_index} A'], texnode.outputs[1])
                                if self.use_terrain_dyemap_output:
                                    material_copy.node_tree.links.new(terrain_node.outputs[0], material_copy.node_tree.nodes.get("Material Output").inputs[0])
                            except:
                                print(f'{material_copy.name}: Index {input_index} out of range for terrain node group')

                            tex_num += 1
                    except Exception as error:
                        print(error)

                    # frame_node = matnodes.new(type='NodeFrame')
                    # frame_node.label = "Have Fun..."
                    # terrain_node.parent = frame_node

def assign_gear_shader(self, objects, Filepath):
    fix_dupe_bones(self, objects)
    for obj in objects:
        #Assign gear shader          
        #Kinda dumb way to check but it works
        diffuse_check = bpy.data.images.get(f'{obj.name[:8]}_albedo{image_extension}')
        if obj.type == 'MESH' and diffuse_check:
            for slot in obj.material_slots:
                if bpy.data.materials.get(f"D2GearShader") is None:
                    addon_dir = os.path.dirname(__file__)
                    full_path = os.path.join(addon_dir, "D2MapImporter/D2GearShader.blend")
                    # Load the node group
                    with bpy.data.libraries.load(full_path) as (data_from, data_to):
                        data_to.materials = ["D2GearShader", "D2ReticleShader"]
                
                #Copy and rename the material
                bpy.data.materials.get(f"D2ReticleShader").use_fake_user = True
                material_copy = bpy.data.materials.get(f"D2GearShader").copy()
                material_copy.name = f"{obj.name[:8]}"
                slot.material = material_copy

                diffuse = bpy.data.images.get(f'{obj.name[:8]}_albedo{image_extension}')
                if diffuse:
                    diffuse.colorspace_settings.name = "sRGB"
                    slot.material.node_tree.nodes.get("Diffuse Texture").image = diffuse

                gstack = bpy.data.images.get(f'{obj.name[:8]}_gstack{image_extension}')
                if gstack:
                    gstack.colorspace_settings.name = "Non-Color"
                    slot.material.node_tree.nodes.get("Gstack Texture").image = gstack

                normal = bpy.data.images.get(f'{obj.name[:8]}_normal{image_extension}')
                if normal:
                    normal.colorspace_settings.name = "Non-Color"
                    slot.material.node_tree.nodes.get("Normal Map").image = normal

                dyemap = bpy.data.images.get(f'{obj.name[:8]}_dyemap{image_extension}')
                if dyemap:
                    dyemap.colorspace_settings.name = "Non-Color"
                    slot.material.node_tree.nodes.get("Dyemap Texture").image = dyemap

                if bpy.data.node_groups.get(f'{self.config["MeshName"]} Shader Preset') is None:
                    bpy.context.view_layer.objects.active = obj
                    bpy.ops.script.python_file_run(filepath=f'{Filepath}/{self.config["MeshName"]}.py')
                    #Remove the unconnected shader from the material before assigning it
                    bpy.data.materials[slot.material.name].node_tree.nodes.remove(bpy.data.materials[slot.material.name].node_tree.nodes.get(f'{self.config["MeshName"]} Shader Preset'))
                
                default_shader = bpy.data.materials[slot.material.name].node_tree.nodes.get(f'Shader Preset')
                default_shader.node_tree = bpy.data.node_groups[f'{self.config["MeshName"]} Shader Preset']

    ######
    for obj in bpy.data.objects: #remove any duplicate materials that may have been created
        for slt in obj.material_slots:
            part = slt.name.rpartition('.')
            if part[2].isnumeric() and part[0] in bpy.data.materials:
                slt.material = bpy.data.materials.get(part[0])

#Fix up duplicate bones/vertex groups
def fix_dupe_bones(self, objects,):
    #Rename vertex weights first
    for obj in objects:
        if obj.type == 'MESH':
            vertex_groups = obj.vertex_groups
            for group in vertex_groups:
                if "." in group.name:
                    part = group.name.split(".")
                    if part[1].isnumeric():
                        group.name = group.name.split(".")[0]

    for obj in objects:
        #Turns out renaming bones automatically renames the vertex weights?
        if obj.type == 'ARMATURE':
                bpy.ops.object.mode_set(mode='EDIT')
                armature = obj.data
                for bone in armature.edit_bones:
                    if "." in bone.name:
                        part = bone.name.split(".")
                        if part[1].isnumeric():
                            print(f'Deleted duplicate bone: {bone.name}')
                            armature.edit_bones.remove(bone)
                    else:
                        key = str(int.from_bytes(bytes.fromhex(bone.name), byteorder="little"))
                        if key in name_mappings:
                            bone.name = name_mappings[key]

        bpy.ops.object.mode_set(mode='OBJECT')

def find_nodes_by_type(material, node_type):
    """ Return a list of all of the nodes in the material
        that match the node type.
        Return an empty list if the material doesn't use
        nodes or doesn't have a tree.
    """
    node_list = []
    if material.use_nodes and material.node_tree:
            for n in material.node_tree.nodes:
                if n.type == node_type:
                    node_list.append(n)
    return node_list

def link_diffuse(material):
    """ Finds at least one image texture in the material
        and at least one Principled shader.
        If they both exist and neither have a link to
        the relevant input socket, connect them.
        There are many ways this can fail.
        if there's no image; if there's no principled
        shader; if the selected image/principled sockets
        are already in use.
        Returns false on any detected error.
        Does not try alternatives if there are multiple
        images or multiple principled shaders.
    """
    it_list = find_nodes_by_type(material, 'TEX_IMAGE')
    s_list = find_nodes_by_type(material, 'BSDF_PRINCIPLED')
    if len(s_list) == 0:
        return False  
    image_node = it_list[0]
    shader_node = s_list[0]
    image_socket = image_node.outputs['Color']
    shader_socket = shader_node.inputs['Base Color']
    if shader_socket.is_linked:
        return
    material.node_tree.links.new(shader_socket, image_socket)

def link_normal(material, num = 0):
    it_list = find_nodes_by_type(material, 'TEX_IMAGE')
    s_list = find_nodes_by_type(material, 'NORMAL_MAP')
    if len(s_list) == 0:
        return False
    image_node = it_list[num]
    #print(len(image_node.items()))
    shader_node = s_list[0]
    if image_node.image.colorspace_settings.name == "Non-Color":
        image_socket = image_node.outputs['Color']
        shader_socket = shader_node.inputs['Color']
        if shader_socket.is_linked:
            return
        material.node_tree.links.new(shader_socket, image_socket)
                     
def cleanup(self):
    print(f"Cleaning up...")
    #Delete all the objects in static_names
    if Is_Map(self):
        for objs in self.static_names.values():
            for name in objs:
                bpy.data.objects.remove(bpy.data.objects[name])
        
    #Removes unused data such as duplicate images, materials, etc.
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)

    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)

    for block in bpy.data.textures:
        if block.users == 0:
            bpy.data.textures.remove(block)

    for block in bpy.data.images:
        if block.users == 0:
            bpy.data.images.remove(block)
    print("Done cleaning up!")

def createprojectionbox(name, corner1, corner2, material):

    # Perform the raycast
    depsgraph = bpy.context.evaluated_depsgraph_get()
    hit, loc, norm, idx, obj, mw = bpy.context.scene.ray_cast(
        depsgraph,
        origin=corner1,  # Starting point of the ray
        direction=(corner2 - corner1).normalized(),  # Direction of the ray
    )

    print("cast_result:", obj)

    # Calculate the positions of the remaining vertices
    vertex_positions = [
        corner1,
        mathutils.Vector((corner1.x, corner1.y, corner2.z)),
        mathutils.Vector((corner1.x, corner2.y, corner1.z)),
        mathutils.Vector((corner1.x, corner2.y, corner2.z)),
        mathutils.Vector((corner2.x, corner1.y, corner1.z)),
        mathutils.Vector((corner2.x, corner1.y, corner2.z)),
        mathutils.Vector((corner2.x, corner2.y, corner1.z)),
        corner2
    ]

    # Define the indices of the cube's faces using the vertex indices
    face_indices = [
        (0, 1, 3, 2),  # Face 0
        (4, 5, 7, 6),  # Face 1
        (0, 1, 5, 4),  # Face 2
        (2, 3, 7, 6),  # Face 3
        (0, 2, 6, 4),  # Face 4
        (1, 3, 7, 5),  # Face 5
    ]

    mesh = bpy.data.meshes.new('Cube')
    obj = bpy.data.objects.new('Cube', mesh)
    
    mat = bpy.data.materials.new(name=material) #set new material to variable
    mat.use_nodes = True
    obj.data.materials.append(mat) #add the material to the object

    obj.name = name
    scene = bpy.context.scene
    scene.collection.objects.link(obj)

    mesh.from_pydata(vertex_positions, [], face_indices)
    mesh.update()

    # UV unwrapping
    mesh.uv_layers.new()
    uv_layer = mesh.uv_layers[0].data

    # Calculate the UV scale
    uv_scale = mathutils.Vector((corner2.x - corner1.x, corner2.y - corner1.y))

    for face in mesh.polygons:
        for loop_index in face.loop_indices:
            loop_vertex_index = mesh.loops[loop_index].vertex_index
            vertex_position = vertex_positions[loop_vertex_index]
            uv = (
                (vertex_position.x - corner1.x) / uv_scale.x,
                (vertex_position.y - corner1.y) / uv_scale.y
            )
            uv_layer[loop_index].uv = uv

def add_to_collection(self):
    # List of object references
    objs = bpy.context.selected_objects
    # Set target collection to a known collection 
    coll_target = bpy.context.scene.collection.children.get(str(self.Name))
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

def Is_Map(self):
    if "Map" in self.type:
        return True
    if "Terrain" in self.type:
        return True
    if "Dynamics" in self.type:
        return True
    if "ActivityEntities" in self.type:
        return True
    else:
        return False

def ShowMessageBox(message = "", title = "Message Box", icon = 'INFO'):
    def draw(self, context):
        self.layout.label(text=message)
    bpy.context.window_manager.popup_menu(draw, title = title, icon = icon)

def check_for_updates():
    global latest_version
    global patch_notes
    global current_version

    repo_name = 'DeltaDesigns/d2-map-importer-addon' # replace with your own repository name
    api_url = f'https://api.github.com/repos/{repo_name}/releases/latest'
    headers = {'Accept': 'application/vnd.github.v3+json'} # use latest version of the API

    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status() # raise an exception if the API returns an error
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
    self.layout.operator(ImportD2Map.bl_idname, text="Destiny 2 Importer (.cfg)", icon_value=custom_icon_col["import"]['D2ICON'].icon_id)

def register():
    import bpy.utils.previews
    
    custom_icon = bpy.utils.previews.new()
    custom_icon.load("D2ICON", os.path.join(icons_dir, "destiny_icon.png"), 'IMAGE')
    custom_icon_col["import"] = custom_icon

    bpy.utils.register_class(ImportD2Map)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

    global update_available 
    update_available = check_for_updates()

def unregister():
    bpy.utils.previews.remove(custom_icon_col["import"])
    bpy.utils.unregister_class(ImportD2Map)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

if __name__ == "__main__":
    register()

name_mappings = {
    #Player
    "68516489": "ForeArm.L",
    "162487657": "Thigh.L",
    "238325804": "Ring_2.R",
    "238325805": "Ring_3.R",
    "238325807": "Ring_1.R",
    "262875985": "Index_1.L",
    "262875986": "Index_2.L",
    "262875987": "Index_3.L",
    "280710669": "Neck_1",
    "280710670": "Neck_2",
    "375707561": "Clav.R",
    "458076469": "Calf.L",
    "523186112": "Pinky_3.R",
    "523186113": "Pinky_2.R",
    "523186114": "Pinky_1.R",
    "542709204": "Eye.R",
    "839315438": "Upper_Eyelid.L",
    "847516523": "Toe.R",
    "976064003": "Clav.L",
    "988249757": "Toe.L",
    "1061868683": "Calf.R",
    "1087804030": "Head",
    "1101907617": "Upper_Lip_Corner.L",
    "1287540002": "Eye.L",
    "1348403735": "UpperArm.R",
    "1462169378": "Lower_Lip_Corner.R",
    "1565559567": "Foot.L",
    "1575008697": "Foot.R",
    "1741390732": "Hand.L",
    "1857732807": "Pelvis",
    "2072385340": "Pinky_1.L",
    "2072385342": "Pinky_3.L",
    "2072385343": "Pinky_2.L",
    "2133354418": "Shoulder_Twist_Fixup.R",
    "2137193665": "Brow_1.L",
    "2362576799": "Thigh.R",
    "2384109844": "Lower_Lip_Corner.L",
    "2453682432": "Thumb_2.R",
    "2453682433": "Thumb_3.R",
    "2453682435": "Thumb_1.R",
    "2527141216": "Middle_3.R",
    "2527141217": "Middle_2.R",
    "2527141218": "Middle_1.R",
    "2592422609": "Ring_1.L",
    "2592422610": "Ring_2.L",
    "2592422611": "Ring_3.L",
    "2608135088": "Middle_1.L",
    "2608135090": "Middle_3.L",
    "2608135091": "Middle_2.L",
    "2666588544": "Utility",
    "2720736209": "UpperArm.L",
    "2728809121": "Spine_1",
    "2728809122": "Spine_2",
    "2728809123": "Spine_3",
    "2996271826": "Jaw",
    "3184076039": "Upper_Lip_Corner.R",
    "3399990467": "Grip.L",
    "3441260707": "ForeArm.R",
    "3470599597": "Wrist_Twist_Fixup.R",
    "3597451020": "Upper_Eyelid.R",
    "3848821786": "Pedestal",
    "3886930732": "Shoulder_Twist_Fixup.L",
    "3932921310": "Hand.R",
    "3940624003": "Wrist_Twist_Fixup.L",
    "4014713625": "Grip.R",
    "4056396384": "Index_2.R",
    "4056396385": "Index_3.R",
    "4056396387": "Index_1.R",
    "4107497571": "Brow_1.R",
    "4256326025": "Thumb_1.L",
    "4256326026": "Thumb_2.L",
    "4256326027": "Thumb_3.L",

    #Hand Cannon
    "670643234": "Hammer",
    "179750274": "Magazine",
    "3172630974": "Cylinder",
    "1065563964": "CraneExtend",
    "1065563967": "CraneRotate",
    "2801973004": "Trigger",

    #Bows
    "152950191": "LongLowerTip",
    "3277629381": "RecurveLowerTip",
    "1450310728": "CompoundLowerOuterCam",
    "569756239": "CompoundLowerOuterString",
    "2233234667": "RecurveLowerLimb",
    "21914261": "LongLowerLimb",
    "886208418": "CompoundLowerOuterLimb",
    "634921014": "CompoundLowerInnerLimb",
    "1211875009": "CompoundLowerInnerCam",
    "2501296090": "CompoundLowerInnerString",
    "3289385034": "Pedestal",
    "2602623454": "LowerString",
    "1924163835": "Arrow",
    "190434716": "Draw",
    "263086803": "UpperString",
    "3159705457": "CompoundUpperInnerLimb",
    "3121359236": "CompoundUpperInnerCam",
    "3221991651": "CompoundUpperInnerString",
    "3640763343": "CompoundUpperOuterLimb",
    "2142955286": "LongUpperLimb",
    "4042000504": "RecurveUpperLimb",
    "3876678289": "CompoundUpperOuterCam",
    "3755358794": "CompoundUpperOuterString",
    "171139942": "RecurveUpperTip",
    "705518836": "LongUpperTip",

    #Heavy GL
    "3885002795": "Sight",
    "4265614694": "CylinderLock",
    "1965908788": "Barrel",
    "946255672": "Cylinder",

    #Linear FR
    "2364075346": "Magazine",
    "2876281604": "Clamp.B",
    "4069453615": "Clamp.F",

    #Light GL
    "179750274": "Magazine",
    "1965908788": "Barrel",
    "3885002795": "Sight",

    #Machine Gun
    "3802038685": "Magazine",
    "1967105434": "ChargingHandle",
    "2427246326": "CoverLatch",
    "1965908788": "Barrel",
    "2665672028": "Cover",
    "4198891668": "Bullet1",
    "4198891671": "Bullet2",
    "4198891670": "Bullet3",
    "4198891665": "Bullet4",
    "4198891664": "Bullet5",
    "4198891667": "Bullet6",
    "4198891666": "Bullet7",
    "4198891677": "Bullet8",
    "4198891676": "Bullet9",

    #Tube Launcher
    "1384189948": "LockingRing_1",
    "179750274": "Magazine",
    "1480745610": "Clip",
    "125467058": "LockingRing_2",

    #Mag Launcher
    "179750274": "Magazine",
    "856221388": "Chamber",
    "1965908788": "Barrel",
    "4228944116": "Grip",
    "2905212365": "MagCover_1",
    "3080347657": "MagCover_2",

    #Sparrow
    "2523032141": "Front",
    "2998140119": "Ski",
    "369029301": "Body",
    "3566855300": "Fin.R",
    "4139241506": "Fin.L",
    "667083509": "Pedal.R",
    "3740636964": "Tail.R",
    "2500435051": "Pedal.L",
    "1397456654": "Tail.L",
}