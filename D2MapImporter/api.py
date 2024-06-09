import D2MapImporter.destiny_importer as globals
import bpy
import D2MapImporter.materials
import os
import D2MapImporter.helper_functions as Helpers

def assign_gear_shader():
    fix_dupe_bones()
    for obj in Helpers.GetCfgParts():
        # Assign gear shader          
        # Kinda dumb way to check but it works
        diffuse_check = Helpers.GetTexture(f'{obj.name[:8]}_albedo')
        if obj.type == 'MESH' and diffuse_check is not None:
            bpy.context.view_layer.objects.active = obj
            for slot in obj.material_slots:
                if bpy.data.materials.get(f"D2GearShader") is None:
                    addon_dir = os.path.dirname(__file__)
                    full_path = os.path.join(addon_dir, "blends/D2GearShader.blend")
                    # Load the node group
                    with bpy.data.libraries.load(full_path) as (data_from, data_to):
                        data_to.materials = ["D2GearShader", "D2ReticleShader"]
                
                # Copy and rename the material
                bpy.data.materials.get(f"D2ReticleShader").use_fake_user = True
                material_copy = bpy.data.materials.get(f"D2GearShader").copy()
                material_copy.name = f"{obj.name[:8]}"
                slot.material = material_copy

                d_tex = Helpers.GetTexture(f'{obj.name[:8]}_albedo')
                if d_tex:
                    diffuse = bpy.data.images.get(d_tex)
                    diffuse.colorspace_settings.name = "sRGB"
                    slot.material.node_tree.nodes.get("Diffuse Texture").image = diffuse

                g_tex = Helpers.GetTexture(f'{obj.name[:8]}_gstack')
                if g_tex:
                    gstack = bpy.data.images.get(g_tex)
                    gstack.colorspace_settings.name = "Non-Color"
                    slot.material.node_tree.nodes.get("Gstack Texture").image = gstack

                n_tex = Helpers.GetTexture(f'{obj.name[:8]}_normal')
                if n_tex:
                    normal = bpy.data.images.get(n_tex)
                    normal.colorspace_settings.name = "Non-Color"
                    slot.material.node_tree.nodes.get("Normal Map").image = normal

                dye_tex = Helpers.GetTexture(f'{obj.name[:8]}_dyemap')
                if dye_tex:
                    dyemap = bpy.data.images.get(dye_tex)
                    dyemap.colorspace_settings.name = "Non-Color"
                    slot.material.node_tree.nodes.get("Dyemap Texture").image = dyemap

                if os.path.exists(path=f'{globals.FilePath}/{globals.Cfg["MeshName"]}.py'):
                    if bpy.data.node_groups.get(f'{globals.Cfg["MeshName"]}') is None:
                        bpy.context.view_layer.objects.active = obj
                        bpy.ops.script.python_file_run(filepath=f'{globals.FilePath}/{globals.Cfg["MeshName"]}.py')
                    #     # Remove the unconnected shader from the material before assigning it
                    #     bpy.data.materials[slot.material.name].node_tree.nodes.remove(bpy.data.materials[slot.material.name].node_tree.nodes.get(f'{globals.Cfg["MeshName"]} Shader Preset'))
                    
                    default_shader = bpy.data.materials[slot.material.name].node_tree.nodes.get(f'Shader Preset')
                    default_shader.node_tree = bpy.data.node_groups[f'{globals.Cfg["MeshName"]}']
                    
                    # TODO: Clean this up
                    for DyeslotsrgbConnections in bpy.context.active_object.active_material.node_tree.nodes:
                        if DyeslotsrgbConnections.name == "Dyemap Texture":
                            for DyemapTOshaderpresetCONNECTIONS in bpy.context.active_object.active_material.node_tree.nodes:
                                if DyemapTOshaderpresetCONNECTIONS.name == "Shader Preset":
                                    bpy.context.active_object.active_material.node_tree.links.new(DyeslotsrgbConnections.outputs[0], DyemapTOshaderpresetCONNECTIONS.inputs[0])
                                    bpy.context.active_object.active_material.node_tree.links.new(DyeslotsrgbConnections.outputs[1], DyemapTOshaderpresetCONNECTIONS.inputs[1])

                    for ShaderPreset in bpy.context.active_object.active_material.node_tree.nodes:
                        if ShaderPreset.name == "Shader Preset":
                            for MainShader in bpy.context.active_object.active_material.node_tree.nodes:
                                if MainShader.name == "D2 PlayerGear Shader":
                                    bpy.context.active_object.active_material.node_tree.links.new(ShaderPreset.outputs['Dye Color A'], MainShader.inputs['Dye Color A'])
                                    bpy.context.active_object.active_material.node_tree.links.new(ShaderPreset.outputs['Dye Color B'], MainShader.inputs['Dye Color B'])
                                    bpy.context.active_object.active_material.node_tree.links.new(ShaderPreset.outputs['Wear Remap_A'], MainShader.inputs['Wear Remap_A'])
                                    bpy.context.active_object.active_material.node_tree.links.new(ShaderPreset.outputs['Wear Remap_B'], MainShader.inputs['Wear Remap_B'])
                                    bpy.context.active_object.active_material.node_tree.links.new(ShaderPreset.outputs['Roughness Remap_A'], MainShader.inputs['Roughness Remap_A'])
                                    bpy.context.active_object.active_material.node_tree.links.new(ShaderPreset.outputs['Roughness Remap_B'], MainShader.inputs['Roughness Remap_B'])
                                    bpy.context.active_object.active_material.node_tree.links.new(ShaderPreset.outputs['Roughness Remap_C'], MainShader.inputs['Roughness Remap_C'])
                                    bpy.context.active_object.active_material.node_tree.links.new(ShaderPreset.outputs['Detail Diffuse'], MainShader.inputs['Detail Diffuse'])
                                    bpy.context.active_object.active_material.node_tree.links.new(ShaderPreset.outputs['Detail Normal'], MainShader.inputs['Detail Normal'])
                                    bpy.context.active_object.active_material.node_tree.links.new(ShaderPreset.outputs['Detail Blends'], MainShader.inputs['Detail Blends'])
                                    bpy.context.active_object.active_material.node_tree.links.new(ShaderPreset.outputs['Worn Detail Blends'], MainShader.inputs['Worn Detail Blends'])
                                    bpy.context.active_object.active_material.node_tree.links.new(ShaderPreset.outputs['Iridescence, Fuzz, Transmission'], MainShader.inputs['Iridescence, Fuzz, Transmission'])    
                                    bpy.context.active_object.active_material.node_tree.links.new(ShaderPreset.outputs['Emission'], MainShader.inputs['Emission'])

    ######
    for obj in bpy.data.objects: # Remove any duplicate materials that may have been created
        for slt in obj.material_slots:
            part = slt.name.rpartition('.')
            if part[2].isnumeric() and part[0] in bpy.data.materials:
                slt.material = bpy.data.materials.get(part[0])

# Fix up duplicate bones/vertex groups
def fix_dupe_bones():
    main_armature = Helpers.GetCfgParts()[0].find_armature()

    # Rename vertex weights if there are duplicates
    for obj in Helpers.GetCfgParts():
        if obj.type == 'MESH':
            vertex_groups = obj.vertex_groups
            for group in vertex_groups:
                if "." in group.name:
                    part = group.name.split(".")
                    if part[1].isnumeric():
                        group.name = group.name.split(".")[0]

    # Remove duplicate skeletons and parent everything to the main skeleton
    for obj in Helpers.GetCfgParts():
        obj_armature = obj.find_armature()
        if obj_armature and (obj_armature == main_armature):
            continue
        if obj_armature:
            bpy.data.objects.remove(obj_armature)

        # Parent part to the main skeleton
        obj.parent = main_armature
        for modifier in obj.modifiers:
            if modifier.type == 'ARMATURE':
                modifier.object = main_armature

    
    bpy.context.view_layer.objects.active = main_armature
    bpy.ops.object.mode_set(mode='EDIT')
    armature = main_armature.data
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