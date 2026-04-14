# Destiny 2/Marathon Importer Addon for Blender 4.0+
Simple Blender addon that simplifies importing Destiny 2 and Marathon rips from Charm/MIDA

Install like a normal Blender addon. **(install the zip from [Releases](https://github.com/DeltaDesigns/d2-map-importer-addon/releases), not just the py)**

How to use: https://github.com/DeltaDesigns/Charm/wiki/Blender-Importing

> [!WARNING]
> Marathon maps are VERY resource heavy.
> * Importing entire Marathon maps can take A VERY VERY LONG TIME. It is recommended to:
> * Import each cfg file into its own blender file, save it, then append everything into one main file.
> * Select "Use Geo Node Instancing" in the options side menu before importing.

# What it CAN do:
- Assemble maps
- Auto assign gear shaders and textures to Player Gear (excluding fx mesh and reticles). - Destiny only at the moment.
- Compatible with DARE/DCG skeletons and IK Player Skeleton
- Geometry node instancing for map statics and decorators.
- Custom camera culling for map decorators (Blender 5.0+)

# What it CAN'T do:
- Materials for anything that isnt player gear. Due to the inconsistency of in-game shaders, they will have to be manually recreated
- Map decals (Projected decals, you can import simple planes at decal locations)
- File your taxes
- Uhhhhh probably something else I can't think of right now

Destiny logo is property of Bungie, Inc.
