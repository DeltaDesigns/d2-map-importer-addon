import D2MapImporter.destiny_importer as globals
import bpy
import mathutils
import json
import os

def add_lights(self):
    print("Importing Lights...")
    if not os.path.exists(globals.FilePath + f"\\Rendering\\Lights.json"):
        print(f"Could not find Lights.Json in '{globals.FilePath}\\Rendering', skipping...")
        return
    
    if bpy.data.collections.get("Lights"):
        print("Lights collection already exists, skipping...")
        return

    bpy.data.collections.new("Lights")
    bpy.context.scene.collection.children.link(bpy.data.collections["Lights"])
    bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children["Lights"]

    with open(globals.FilePath + f"\\Rendering\\Lights.json", 'r') as f:
        Cfg = json.load(f)

    for name, data in Cfg.items():
        light_type = data["Type"]
        match data["Type"]:
            case "Line":
                light_type = "Area"
            case "Shadowing":
                light_type = "Spot"
        
        for instance in data["Instances"]:
            if bpy.data.lights.get(f"{name}") is None:
                light_data = bpy.data.lights.new(name=f"{name}", type=light_type.upper())
                light_object = bpy.data.objects.new(name=f"{name}", object_data=light_data)
                bpy.context.collection.objects.link(light_object)

                color = [data["Color"][0], data["Color"][1],data["Color"][2]] # Added W but don't know if theres any purpose for it
                if color == [0,0,0] and self.override_light_color:
                    color = [1,1,1]
                light_object.data.color = color
                light_object.data.energy = self.light_intensity_override
                light_object.data.use_shadow = False
                light_object.data.cycles.use_shadow = False
                light_object.data.use_custom_distance = True

                if light_object.data.type == 'SPOT':
                    if data["Type"] == "Shadowing":
                        light_object.data.use_shadow = True 
                        light_object.data.cycles.use_shadow = True
                        #light_object.data.energy = self.light_intensity_override * light_object.data.color.v # meh
                        
                    light_object.data.spot_size = instance["Scale"][0]
                    light_object.data.cutoff_distance = instance["Scale"][1]

                elif light_object.data.type == 'AREA':
                    light_object.data.shape = 'RECTANGLE'
                    light_object.data.size = instance["Scale"][1] * 0.85
                    light_object.data.size_y = instance["Scale"][0] * 0.85
                    light_object.data.cutoff_distance = instance["Scale"][2]
                    
                else:
                    #light_object.data.shadow_soft_size = data["Size"][0] #data["Range"]/4 # idk
                    light_object.data.cutoff_distance = instance["Scale"][2]
            else:
                light_object = bpy.data.objects.get(f"{name}").copy()
                bpy.context.collection.objects.link(light_object)
            
            location = [instance["Translation"][0], instance["Translation"][1], instance["Translation"][2]]
            quat = mathutils.Quaternion([instance["Rotation"][3], instance["Rotation"][0], instance["Rotation"][1], instance["Rotation"][2]]) #WXYZ

            light_object.location = location
            light_object.rotation_mode = 'QUATERNION'
            if light_object.data.type == 'SPOT' or light_object.data.type == 'AREA': # this seeeeems to work...?
                light_object.delta_rotation_quaternion = quat
                light_object.rotation_quaternion =  mathutils.Quaternion([0.5,0.5,-0.5, -0.5 if light_object.data.type == 'SPOT' else 0.5])
            else:
                light_object.rotation_quaternion = quat

    print("Imported Lights.")