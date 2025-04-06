import D2MapImporter.destiny_importer as globals
import bpy
import os
import json
from .helper_functions import *

def assign_materials():
    print("Assigning materials...")
    global image_extension
    materials = bpy.data.materials
   
    for obj in bpy.data.objects: # Remove any duplicate materials that may have been created
        if obj.type == 'MESH':
            for slt in obj.material_slots:
                part = slt.name.rpartition('.')
                if part[2].isnumeric() and part[0] in materials:
                    slt.material = materials.get(part[0])
    
    #json_files = [f for f in os.listdir(f'{globals.FilePath}\\Materials') if f.endswith(".json")]

    for part_name, part_data in globals.Cfg["Parts"].items():
        for geom_name, material_hash in part_data.items():
            if not os.path.exists(os.path.join(globals.AssetsPath, f'Materials\\{material_hash}.json')):
                print(f"Could not find material {material_hash}.Json in '{globals.FilePath}\\Materials', skipping...")
                continue

            with open(os.path.join(globals.AssetsPath, f'Materials\\{material_hash}.json'), 'r') as f:
                data = json.load(f)
            
            ps_textures = data["Material"]["Pixel"]["Textures"]
            vs_textures = data["Material"]["Vertex"]["Textures"]
            
            try:
                material = bpy.data.materials[data["Hash"]]

                # Get Rasterizer settings
                rasterizer = data["RenderStates"].get("Rasterizer")
                cull_mode = rasterizer.get("CullMode") if rasterizer else None

                # Set backface culling
                if cull_mode == "None":
                    material.use_backface_culling = False if cull_mode == "None" else True

                if 'Decorators' in globals.Type or 'SkyObjects' in globals.Type:
                    if bpy.app.version < (4, 3, 0):
                        material.shadow_method = 'NONE'
                
                matnodes = material.node_tree.nodes
                if matnodes.find('Principled BSDF') != -1:
                    matnodes['Principled BSDF'].inputs['Metallic'].default_value = 0 

                # To make sure the current material already doesnt have at least one texture node
                if not len(find_nodes_by_type(material, 'TEX_IMAGE')) > 0:
                    tex_num = 0 # To keep track of the current position in the list
                    for n, info in ps_textures.items():
                        tex_image = GetTexture(info["Hash"])
                        colorspace = info["Colorspace"]

                        texnode = matnodes.new('ShaderNodeTexImage')
                        texnode.hide = True
                        texnode.location = (-370.0, 200.0 + (float(tex_num)*-1.1)*50) # Offsetting

                        if tex_image:
                            texture = bpy.data.images.get(tex_image)
                            texnode.label = texture.name
                            texture.colorspace_settings.name = colorspace
                            texture.alpha_mode = "CHANNEL_PACKED"
                            texnode.image = texture      # Assign the texture to the node

                            # Assign the first texture to material's diffuse just to help a little, good luck o7
                            link_diffuse(material)

                        tex_num += 1
            except KeyError as keyE:
                print(f"{keyE}: ", data["Hash"])
            except Exception as e:
                print(e)

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

def add_terrain_dyemaps(self):
    for obj in GetCfgParts():
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
                        full_path = os.path.join(addon_dir, "blends/D2TerrainNode.blend")

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
                        num_textures = len(globals.Cfg["TerrainDyemaps"][prefix])

                        # Calculate the starting index for texture assignment
                        start_index = num_inputs - num_textures

                        # Iterate through the textures and assign them to the node inputs
                        for i, tex in enumerate(globals.Cfg["TerrainDyemaps"][prefix]):
                            input_index = (start_index + i + 1) % (num_inputs + 1)  # Adjusted for 1-based indexing

                            texnode = matnodes.new('ShaderNodeTexImage')
                            texnode.hide = True
                            texnode.location = (-360.0, 1200.0 + (float(tex_num) * -1.1) * 50)  # Shitty offsetting

                            tex_image = GetTexture(tex)
                            texture = bpy.data.images.get(tex_image)
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

def create_material(self, name):
    if not os.path.exists(os.path.join(globals.AssetsPath, f'Materials\\{name}.json')):
        print(f"Could not find material {name}.Json in '{globals.FilePath}\\Materials', skipping...")
        return
    
    with open(os.path.join(globals.AssetsPath, f'Materials\\{name}.json'), 'r') as f:
        data = json.load(f)
            
    ps_textures = data["Material"]["Pixel"]["Textures"]
    vs_textures = data["Material"]["Vertex"]["Textures"]
    
    try:
        material = bpy.data.materials.new(name=data["Hash"])
        material.use_nodes = True

        material = bpy.data.materials[data["Hash"]]

        # Get Rasterizer settings
        rasterizer = data["RenderStates"].get("Rasterizer")
        cull_mode = rasterizer.get("CullMode") if rasterizer else None

        # Set backface culling
        if cull_mode == "None":
            material.use_backface_culling = False if cull_mode == "None" else True

        if "TRANSPARENT" in data["Scopes"]:
            if bpy.app.version < (4, 3, 0):
                material.shadow_method = 'NONE'
        
        matnodes = material.node_tree.nodes
        if matnodes.find('Principled BSDF') != -1:
            matnodes['Principled BSDF'].inputs['Metallic'].default_value = 0 

        # To make sure the current material already doesnt have at least one texture node
        if not len(find_nodes_by_type(material, 'TEX_IMAGE')) > 0:
            tex_num = 0 # To keep track of the current position in the list
            for n, info in ps_textures.items():
                tex_image = GetTexture(info["Hash"])
                colorspace = info["Colorspace"]

                texnode = matnodes.new('ShaderNodeTexImage')
                texnode.hide = True
                texnode.location = (-370.0, 200.0 + (float(tex_num)*-1.1)*50) # Offsetting

                if tex_image:
                    texture = bpy.data.images.get(tex_image)
                    texnode.label = texture.name
                    texture.colorspace_settings.name = colorspace
                    texture.alpha_mode = "CHANNEL_PACKED"
                    texnode.image = texture      # Assign the texture to the node

                    # Assign the first texture to material's diffuse just to help a little, good luck o7
                    link_diffuse(material)

                tex_num += 1
    except KeyError as keyE:
        print(f"{keyE}: ", data["Hash"])
    except Exception as e:
        print(e)