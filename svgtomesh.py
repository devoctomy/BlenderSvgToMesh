import bpy
import os
import sys
from xml.dom.minidom import parse
from xml.dom.minidom import Node
from os import listdir
from os.path import isfile, join

#----------------------------------
#Configuration
#----------------------------------
deleteOnBoolean = True
extrudeRooms = True
createOuter = True
booleanOuterWithRooms = True

roomsToCreate = [] #[ "room1", "corridor1", "room2" ]
roomKeys = {}
roomKeys['#ff0000'] = ("Room", 0, 2.8)              #Room
roomKeys['#00ff00'] = ("Corridor", 0, 2.8)          #Corridor
roomKeys['#ffff00'] = ("CeilingHole", 2.7, 0.2)     #Ceiling hole
roomKeys['#0000ff'] = ("Column", 0, 0)              #Column
#----------------------------------

def applyBoolean(op, obj1, obj2, deleteObj2):
    print("Performing union of '" + obj1.name + "' with '" + obj2.name + "'")
    bpy.context.view_layer.objects.active = obj1
    bpy.ops.object.modifier_add(type='BOOLEAN')
    bpy.context.object.modifiers["Boolean"].operation = op
    bpy.context.object.modifiers["Boolean"].object = obj2
    bpy.ops.object.modifier_apply(apply_as='DATA', modifier="Boolean")
    if deleteObj2:
        obj2.select_set(True)
        bpy.ops.object.delete()                 

def CompositePlane(objname, px, py, pz, width, height, subWidth, subHeight):
    xCount = int(width / subWidth);
    yCount = int(height / subHeight);
    if xCount == 0:
        xCount = 1
    if yCount == 0:
        yCount = 1
    xOffset = (width / 2) - (subWidth / 2)
    yOffset = (height / 2) - (subHeight / 2)
    planes = []
    for curY in range(0, yCount):
        for curX in range(0, xCount):           
            plane = CreatePlane(objname + ".plane" + str(len(planes)), px + (curX * subWidth) - xOffset, py - ((curY * subHeight) - yOffset), pz, subWidth, subHeight)
            planes.append(plane)
    
    return planes

def CreatePlane(objname, px, py, pz, width, height):
    print("Creating plane " + str(px) + "," + str(py) + "," + str(pz) + ", width = " + str(width) + ", height = " + str(height))
    myvertex = []
    myfaces = []
    
    mypoint = [(0-width/2, 0-height/2, 0.0)]
    myvertex.extend(mypoint)
    mypoint = [(width/2, 0-height/2, 0.0)]
    myvertex.extend(mypoint)
    mypoint = [(0-width/2, height/2, 0.0)]
    myvertex.extend(mypoint)
    mypoint = [(width/2, height/2, 0.0)]
    myvertex.extend(mypoint)

    myface = [(0, 1, 3, 2)]
    myfaces.extend(myface)
    mymesh = bpy.data.meshes.new(objname)
    myobject = bpy.data.objects.new(objname, mymesh)
    bpy.context.collection.objects.link(myobject)

    mymesh.from_pydata(myvertex, [], myfaces)
    mymesh.update(calc_edges=True)
    myobject.location.x = px
    myobject.location.y = py
    myobject.location.z = pz

    return myobject

def JoinObjects(objects, newName):
    bpy.context.view_layer.objects.active = objects[0]
    for o in objects:
        o.select_set(True)      
    bpy.ops.object.join()
    objects[0].name = newName
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.remove_doubles()
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')

    return objects[0]

def ExtrudeUp(obj, offset):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.remove_doubles()
    bpy.ops.mesh.extrude_region_move(TRANSFORM_OT_translate={"value":(0, 0, offset)})
    bpy.ops.object.mode_set(mode='OBJECT')

filepath = bpy.data.filepath
directory = os.path.dirname(filepath)

print("Enumerating levels")
mypath = directory + "\\input\\"
onlyfiles = [f for f in listdir(mypath) if isfile(join(mypath, f))]
levelWidth = 0
levelHeight = 0
toExtrude = {}
toRemoveFromCeling = {}
allPlanes = []
allCelingDrops = {}
firstRoomRectId = "unset"
postJoinObjects = []
for f in onlyfiles:
    if f.endswith("svg"):
        print("Processing level file '" + mypath + f + "'")
        domData = parse(mypath + f)
        
        levelWidth = float(domData.documentElement.getAttribute("width"))
        levelHeight = float(domData.documentElement.getAttribute("height"))
            
        gElement = domData.documentElement.getElementsByTagName("g")[0]
        transform = gElement.getAttribute("transform")
        transformLen = len(transform)
        transformParts = transform[10:transformLen-1].split(",")
        offsetX = float(transformParts[0])
        offsetY = float(transformParts[1])
        
        rectElements = gElement.getElementsByTagName("rect")
        
        for rect in rectElements:
            id = rect.getAttribute("id")            
            if len(roomsToCreate) == 0 or id in roomsToCreate:
                print("Processing rect " + id)
                style = rect.getAttribute("style")
                styleParts = style.split(";")
                fillParts = styleParts[0].split(":")
                x = rect.getAttribute("x")
                y = rect.getAttribute("y")
                width = rect.getAttribute("width")
                height = rect.getAttribute("height")
                                
                key = roomKeys[fillParts[1]]            
                if key[0] == "Room" or key[0] == "Corridor":
                    print("Creating room or corridor '" + id + "'")
                    planeXPos = float(x) + float(width)/2
                    planeYPos = (float(y) + float(height)/2) * -1                  
                    planes = CompositePlane(id + ".floor." + key[0], planeXPos + offsetX, planeYPos - offsetY, 0, float(width), float(height), 5, 5)
                    allPlanes.extend(planes)
                    
                    if key[0] == "Corridor":
                        ceilingDropPlanes = CompositePlane(id + ".ceiling." + key[0], planeXPos + offsetX, planeYPos - offsetY, 8, float(width), float(height), 5, 5)
                        celingDrop = JoinObjects(ceilingDropPlanes, id)
                        allCelingDrops[id + ".ceiling."] = celingDrop

                if key[0] == "Column":
                    print("Creating comlumn '" + id + "'")
                    planeXPos = float(x) + float(width)/2
                    planeYPos = (float(y) + float(height)/2) * -1                  
                    planes = CompositePlane(id + ".floor." + key[0], planeXPos + offsetX, planeYPos - offsetY, 0, float(width), float(height), 5, 5)
                    for p in planes:
                        toExtrude[p.name] = p
                        postJoinObjects.append(p)
                
                if key[0] == "CeilingHole":
                    print("Creating ceiling hole '" + id + "'")
                    planeXPos = float(x) + float(width)/2
                    planeYPos = (float(y) + float(height)/2) * -1
                    plane = CreatePlane(id + "." + key[0], planeXPos + offsetX, planeYPos - offsetY, 0, float(width), float(height))
                    toRemoveFromCeling[id] = plane

bpy.context.view_layer.objects.active = allPlanes[0]
for p in allPlanes:
    p.select_set(True)      
bpy.ops.object.join()
allPlanes[0].name = "Rooms"
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.remove_doubles()
bpy.ops.object.mode_set(mode='OBJECT')
rootObject = bpy.data.objects["Rooms"]
bpy.ops.object.select_all(action='DESELECT')    
toExtrude["Rooms"] = bpy.data.objects["Rooms"]   
    
if extrudeRooms == True:
    print("Extruding rooms")
    for e in toExtrude:
        ExtrudeUp(toExtrude[e], 10)
        
    for cd in allCelingDrops:
        ExtrudeUp(allCelingDrops[cd], 2)
        postJoinObjects.append(allCelingDrops[cd])

if createOuter == True:
    extraWidth = levelWidth + 10
    extraHeight = levelHeight + 10
    CreatePlane("Outer", (extraWidth/2) - 5, ((extraHeight/2) * -1) + 5, -2, extraWidth, extraHeight)
    ExtrudeUp(bpy.data.objects["Outer"], 14)

    if booleanOuterWithRooms == True:
        applyBoolean("DIFFERENCE", bpy.data.objects["Outer"], bpy.data.objects["Rooms"], deleteOnBoolean)
        rootObject = bpy.data.objects["Outer"]
        
    postJoinObjects.append(bpy.data.objects["Outer"])

for r in toRemoveFromCeling:
    curObj = toRemoveFromCeling[r]
    curObj.location.z += 10
    ExtrudeUp(curObj, 14)
    applyBoolean("DIFFERENCE", bpy.data.objects["Outer"], curObj, deleteOnBoolean)

JoinObjects(postJoinObjects, "LevelMesh")

#if groupAll:
#    for o in bpy.data.objects:
#        if o.name != rootObject.name:
#            matrix = o.matrix_world.copy()
#            o.parent = rootObject
#            o.matrix_world = matrix
        
#if centre == True:
#    print("Centering mesh")
#    bpy.context.view_layer.objects.active = rootObject
#    bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_MASS')
#    rootObject.location = (0,0,0)