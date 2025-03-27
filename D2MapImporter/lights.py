import D2MapImporter.destiny_importer as globals
import bpy
import mathutils
import json

def add_lights(self):
    with open(globals.FilePath + f"\\Rendering\\Lights.json", 'r') as f:
        Cfg = json.load(f)

    for name, data in Cfg.items():
        light_type = data["Type"]
        match data["Type"]:
            case "Line":
                light_type = "Area"
            case "Shadowing":
                light_type = "Spot"
        
        if bpy.data.lights.get(f"{name}") is None:
            light_data = bpy.data.lights.new(name=f"{name}", type=light_type.upper())
            light_object = bpy.data.objects.new(name=f"{name}", object_data=light_data)
            bpy.context.collection.objects.link(light_object)

            color = data["Color"]
            if data["Color"] == [0,0,0] and self.override_light_color:
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
                    
                light_object.data.spot_size = data["Size"][0]
                light_object.data.cutoff_distance = data["Range"]
            elif light_object.data.type == 'AREA':
                light_object.data.shape = 'RECTANGLE'
                light_object.data.size = data["Size"][1] * 0.85
                light_object.data.size_y = data["Size"][0] * 0.85
                light_object.data.cutoff_distance = data["Range"]
            else:
                #light_object.data.shadow_soft_size = data["Size"][0] #data["Range"]/4 # idk
                light_object.data.cutoff_distance = data["Range"]
        else:
            light_object = bpy.data.objects.get(f"{name}").copy()
            bpy.context.collection.objects.link(light_object)
        
        location = [data["Translation"][0], data["Translation"][1], data["Translation"][2]]
        quat = mathutils.Quaternion([data["Rotation"][3], data["Rotation"][0], data["Rotation"][1], data["Rotation"][2]]) #WXYZ

        light_object.location = location
        light_object.rotation_mode = 'QUATERNION'
        if light_object.data.type == 'SPOT' or light_object.data.type == 'AREA': # this seeeeems to work...?
            light_object.delta_rotation_quaternion = quat
            light_object.rotation_quaternion =  mathutils.Quaternion([0.5,0.5,-0.5, -0.5 if light_object.data.type == 'SPOT' else 0.5])
        else:
            light_object.rotation_quaternion = quat