import bpy
import D2MapImporter.destiny_importer as globals
import os
import glob

def ShowMessageBox(message = "", title = "Message Box", icon = 'INFO'):
    def draw(self, context):
        self.layout.label(text=message)
    bpy.context.window_manager.popup_menu(draw, title = title, icon = icon)

def Is_Map(type):
    return any(x in type for x in ["Map", "Terrain", "Dynamics", "ActivityEntities"])

def add_to_collection(name):
    # List of object references
    objs = bpy.context.selected_objects
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
    image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.gif', '*.tiff', '*.webp']

    # Iterate through extensions and search for matching files
    for extension in image_extensions:
        pattern = os.path.join(globals.FilePath + "/Textures/", f"{image_name}{extension[1:]}")  # Remove '*' from extension
        files = glob.glob(pattern)
        if files:  # If any files are found, return the first one
            bpy.data.images.load(files[0], check_existing = True)
            img = os.path.basename(files[0])
            print(f'Loaded {img}')
            return img
    return None

def cleanup():
    print(f"Cleaning up...")
    bpy.ops.outliner.orphans_purge()

    # Removes unused data such as duplicate images, materials, etc.
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