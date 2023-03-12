bl_info = {
    "name": "Destiny 2 Map Importer",
    "author": "DeltaDesigns, Montegue/Monteven",
    "version": (0, 3, 2),
    "blender": (3, 0, 0),
    "location": "File > Import",
    "description": "Import Destiny 2 Maps exported from Charm",
    "warning": "BETA",
    "category": "Import",
    "package": "d2_map_importer"
    }

import bpy
from bpy.props import *
import json
import mathutils
import os

# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty, CollectionProperty
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
            description="Combine all parts of a model into one mesh",
            default=True,
            )

    use_import_materials: BoolProperty(
            name="Import Textures",
            description="Imports textures and tries to apply them to the models",
            default=True,
            )

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.label(text="Current Version: " + current_version)
        box.label(text="Options:")
        box.prop(self, 'combine_statics')
        box.prop(self, 'use_import_materials')

        if update_available:
            box = layout.box()
            box.label(text="Update available: " + latest_version)
            box.operator("wm.url_open", text="Get Latest Release").url = "https://github.com/DeltaDesigns/d2-map-importer-addon/releases/latest"

    def execute(self, context):        # execute() is called when running the operator.

        #Deselect all objects just in case 
        bpy.ops.object.select_all(action='DESELECT')

        if self.files:
            ShowMessageBox(f"Importing...", "This might take some time! (Especially on multiple imports)", 'ERROR')
            #Filepath = os.path.abspath(bpy.context.space_data.text.filepath+"/..")
            dirname = os.path.dirname(self.filepath)
            for file in self.files:
                self.Filepath = dirname #os.path.join(dirname, file.name)
                
                print(f"File: {file.name}")
                print(f"Name: {file.name[:-9]}")
                print(f"Path: {dirname}")

                #To give the message box a chance to show up
                assemble_map(self, file, self.Filepath)

        return {'FINISHED'}            # Lets Blender know the operator finished successfully.

#Where all the fun happens..

def assemble_map(self, file, Filepath):
    self.static_names = {}

    Name = file.name[:-9] #Removes the _info.cfg from the name
    
    self.config = json.load(open(Filepath + f"\\{file.name}"))
    
    if "Type" in self.config:
        self.type = self.config["Type"]

    #Skip if theres nothing to import
    if self.config["Instances"].items().__len__() == 0 and "Map" in self.type:
        print(f"No instances found in {Name}, skipping...")
        return
 
    print(f"Starting import on {self.type}: {Name}")

    #make a collection with the name of the imported fbx for the objects
    bpy.data.collections.new(str(Name))
    bpy.context.scene.collection.children.link(bpy.data.collections[str(Name)])
    bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[str(Name)]

    bpy.ops.import_scene.fbx(filepath=Filepath+ "\\" + Name + ".fbx", use_custom_normals=True, ignore_leaf_bones=True, automatic_bone_orientation=True) #Just imports the fbx, no special settings needed
    
    add_to_collection(self) 

    newobjects = bpy.data.collections[str(Name)].objects

    print(f"Imported {self.type}: {Name}")
    
    #Merge statics, create instances for maps only
    if Is_Map(self):
        if self.combine_statics:
            print("Merging Map Statics... ")
            tmp = []
            for obj in newobjects:
                #deselect all objects
                bpy.ops.object.select_all(action='DESELECT')
                tmp.append(obj.name[:8])

            #merge static parts into one object
            if len(self.config["Parts"].items()) != 1:
                for obj in tmp:
                    bpy.ops.object.select_all(action='DESELECT')
                    for meshes, mats in self.config["Parts"].items():
                        if meshes[:8] == obj and meshes in bpy.context.view_layer.objects:
                            print(meshes + " belongs to " + obj)
                            bpy.data.objects[meshes].select_set(True)
                            bpy.context.view_layer.objects.active = bpy.data.objects[meshes]
                    bpy.ops.object.join()
                bpy.ops.outliner.orphans_purge()

        newobjects = [] #Clears the list just in case
        newobjects = bpy.data.collections[str(Name)].objects #Readds the objects in the collection to the list

        for x in newobjects:
            if len(self.config["Instances"].items()) <= 1 and len(self.config["Parts"].items()) <= 1: #Fix for error that occurs when theres only 1 object in the fbx
                for newname, value in self.config["Instances"].items():
                    x.name = newname

            obj_name = x.name[:8]
            if obj_name not in self.static_names.keys():
                self.static_names[obj_name] = []
            self.static_names[obj_name].append(x.name)

        print("Instancing...")

        for static, instances in self.config["Instances"].items():
            try:  # fix this
                parts = self.static_names[static]
            except:
                print(f"Failed on {static}. FBX may contain only 1 object")
                continue

            for part in parts:
                for instance in instances:
                    if bpy.data.objects[part].parent: #For dynamics with skeletons, need to copy the skeleton and meshes THEN reparent the copied meshes to the copied skeleton and change its armature modifier...
                        if bpy.data.objects[part].parent.type == 'ARMATURE':
                            ob_copy = bpy.data.objects[part].parent.copy()
                            bpy.context.scene.collection.objects.link(ob_copy)
                            print(f"Object '{bpy.data.objects[part].name}' is parented to an armature '{ob_copy.name}'")

                            # Loop through the collections that the armature is linked to (idk why it does this)
                            for collection in ob_copy.users_collection:
                                # Unlink the armature from the collection
                                collection.objects.unlink(ob_copy)

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
                    #Reminder that blender uses WXYZ, the order in the confing file is XYZW, so W is always first
                    quat = mathutils.Quaternion([instance["Rotation"][3], instance["Rotation"][0], instance["Rotation"][1], instance["Rotation"][2]])

                    ob_copy.location = location
                    ob_copy.rotation_mode = 'QUATERNION'
                    ob_copy.rotation_quaternion = quat
                    ob_copy.scale = [instance["Scale"]]*3
    
        if "Terrain" in self.type:
            for x in newobjects:
                x.select_set(True)
                bpy.ops.object.rotation_clear(clear_delta=False) #Clears the rotation of the terrain

    if not Is_Map(self):
        for x in newobjects:
            print(x)
            if len(self.config["Parts"].items()) <= 1: #Fix for error that occurs when theres only 1 object in the fbx
                for newname, value in self.config["Parts"].items():
                    x.name = newname

        for x in newobjects:
            x.select_set(True)
            #Clear the scale and rotation of the entity
            bpy.ops.object.rotation_clear(clear_delta=False)
            bpy.ops.object.scale_clear(clear_delta=False)

    if self.use_import_materials:
        assign_materials(self)

    cleanup(self)

def assign_materials(self):
    print("Assigning materials...")
    
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
                        bpy.data.objects[name].active_material.name = mat

    for obj in bpy.data.objects: #remove any duplicate materials that may have been created
        for slt in obj.material_slots:
            part = slt.name.rpartition('.')
            if part[2].isnumeric() and part[0] in materials:
                slt.material = materials.get(part[0])
        
    #Get all the images in the directory and load them
    #Should probably change this to only load the textures included in the cfg, as to not load unneeded textures
    for img in os.listdir(self.Filepath + "/Textures/"):
        if img.endswith(".png"):
            bpy.data.images.load(self.Filepath + "/Textures/" + f"/{img}", check_existing = True)
            print(f"Loaded {img}")
    
    #New way of getting info from cfg, thank you Mont
    d = {x : y["PS"] for x, y in self.config["Materials"].items()}
    
    for k, mat in d.items():
        matnodes = bpy.data.materials[k].node_tree.nodes
        if matnodes.find('Principled BSDF') != -1:
            matnodes['Principled BSDF'].inputs['Metallic'].default_value = 0 

        #To make sure the current material already doesnt have at least one texture node
        if not len(find_nodes_by_type(bpy.data.materials[k], 'TEX_IMAGE')) > 0: #
            tex_num = 0 #To keep track of the current position in the list
            for n, info in mat.items():
                #current_image = "PS_" + str(n) + "_" + info["Hash"] + ".png"
                current_image = info["Hash"] + ".png"
                
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

                    #assign a texture to material's diffuse and normal just to help a little 
                    if texture.colorspace_settings.name == "sRGB":     
                        link_diffuse(bpy.data.materials[k])
                    if texture.colorspace_settings.name == "Non-Color":
                        if int(tex_num) == 0:
                            link_diffuse(bpy.data.materials[k])
                        else:
                            link_normal(bpy.data.materials[k], int(tex_num))
                tex_num += 1
                
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
        for name in self.static_names.values():
            bpy.data.objects.remove(bpy.data.objects[name[0]])
        
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
    else:
        return False

def ShowMessageBox(message = "", title = "Message Box", icon = 'INFO'):
    def draw(self, context):
        self.layout.label(text=message)
    bpy.context.window_manager.popup_menu(draw, title = title, icon = icon)

import requests
import json

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

    if latest_version != current_version:
        return True


def menu_func_import(self, context):
    self.layout.operator(ImportD2Map.bl_idname, text="Destiny 2 Map Importer (.cfg)", icon_value=custom_icon_col["import"]['D2ICON'].icon_id)

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

# This allows you to run the script directly from Blender's Text editor
# to test the add-on without having to install it.
if __name__ == "__main__":
    register()