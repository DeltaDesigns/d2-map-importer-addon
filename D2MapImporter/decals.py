import D2MapImporter.destiny_importer as globals
import bpy
import mathutils
import json
import os
from .materials import *

def add_decal_planes(self):
    print("Creating Decal planes...")
    if not os.path.exists( globals.FilePath + f"\\Rendering\\Decals.json"):
        print(f"Could not find Decals.Json in '{globals.FilePath}\\Rendering', skipping...")
        return
    
    if bpy.data.collections.get("Decal Planes"):
        print("Decals collection already exists, skipping...")
        return

    bpy.data.collections.new("Decal Planes")
    bpy.context.scene.collection.children.link(bpy.data.collections["Decal Planes"])
    bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children["Decal Planes"]
   
    with open(globals.FilePath + f"\\Rendering\\Decals.json", 'r') as f:
        Cfg = json.load(f)

    for name, data in Cfg.items():
        if bpy.data.materials.get(name) is None:
            create_material(name)

        plane = bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0))
        plane = bpy.context.view_layer.objects.active
        plane.name = name
        if plane.data.materials:
            plane.data.materials[0] = bpy.data.materials[name]
        else:
            plane.data.materials.append(bpy.data.materials[name])
        
        for i, instance in enumerate(data["Instances"]):
            location = [instance["Translation"][0], instance["Translation"][1], instance["Translation"][2]]
            quat = mathutils.Quaternion([instance["Rotation"][3], instance["Rotation"][0], instance["Rotation"][1], instance["Rotation"][2]]) #WXYZ
            scale = [instance["Scale"][0], instance["Scale"][1], instance["Scale"][2]]

            plane.location = location
            plane.rotation_mode = 'QUATERNION'
            plane.rotation_quaternion = quat
            plane.scale = scale

            if i != len(data["Instances"]) - 1:
                plane = plane.copy()
                bpy.context.collection.objects.link(plane)

    print("Imported Decal Planes.")