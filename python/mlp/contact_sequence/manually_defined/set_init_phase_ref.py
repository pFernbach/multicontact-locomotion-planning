from mlp.utils.cs_tools import addPhaseFromConfig, createPhaseFromConfig
import multicontact_api
from multicontact_api import ContactSequence
import mlp.viewer.display_tools as display_tools
from pinocchio import SE3
from numpy import array
from mlp.utils.cs_tools import walk
from talos_rbprm.talos import Robot  # change robot here
multicontact_api.switchToNumpyArray()

ENV_NAME = "multicontact/plateforme_surfaces_noscale"

fb, v = display_tools.initScene(Robot, ENV_NAME, False)
gui = v.client.gui
sceneName = v.sceneName
cs = ContactSequence(0)

cs_platforms = ContactSequence(0)
cs_platforms.loadFromBinary("talos_plateformes_legs_appart.cs")
p0_old = cs_platforms.contactPhases[0]

q = [   0.0,
        0.0,
        1.02127,
        0.0,
        0.0,
        0.0,
        1.,  # Free flyer
        0.0,
        0.0,
        -0.411354,
        0.859395,
        -0.448041,
        -0.001708,  # Left Leg
        0.0,
        0.0,
        -0.411354,
        0.859395,
        -0.448041,
        -0.001708,  # Right Leg
        0.0,
        0.006761,  # Chest
        0.40,
        0.24,
        -0.6,
        -1.45,
        0.0,
        -0.0,
        0.,
        -0.005,  # Left Arm
        -0.4,
        -0.24,
        0.6,
        -1.45,
        0.0,
        0.0,
        0.,
        -0.005,  # Right Arm
        0.,
        0.
    ] + [0]*6

q[:3] = p0_old.q_init[0:3]
addPhaseFromConfig(fb, cs, q, [fb.rLegId, fb.lLegId])

i = 2
while i <= cs_platforms.size():
    vars = cs_platforms.contactPhases[i].getContactsRepositioned(cs_platforms.contactPhases[i - 2])
    assert len(vars) == 1
    var = vars[0]
    cs.moveEffectorToPlacement(var,cs_platforms.contactPhases[i].contactPatch(var).placement)
    i+=2

display_tools.displaySteppingStones(cs, gui, sceneName, fb)
filename = "talos_platformes.cs"
print("Write contact sequence binary file : ", filename)
cs.saveAsBinary(filename)