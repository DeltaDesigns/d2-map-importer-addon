import D2MapImporter.destiny_importer as globals
import bpy
import mathutils

def add_lights(self):
    if "Lights" in globals.Cfg:
        for name, lights in globals.Cfg["Lights"].items():
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
                    quat = mathutils.Quaternion([data["Rotation"][3], data["Rotation"][0], data["Rotation"][1], data["Rotation"][2]])

                    light_object.location = location
                    light_object.rotation_mode = 'QUATERNION'
                    light_object.rotation_quaternion = quat
                else:
                    light_object = bpy.data.objects.get(data["Type"] + f"_{name}").copy()
                    bpy.context.collection.objects.link(light_object)

                    location = [data["Translation"][0], data["Translation"][1], data["Translation"][2]]
                    quat = mathutils.Quaternion([data["Rotation"][3], data["Rotation"][0], data["Rotation"][1], data["Rotation"][2]])

                    light_object.location = location
                    light_object.rotation_mode = 'QUATERNION'
                    light_object.rotation_quaternion = quat