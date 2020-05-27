from mlp.utils.cs_tools import addPhaseFromConfig
import multicontact_api
from multicontact_api import ContactSequence
import mlp.viewer.display_tools as display_tools
from pinocchio import SE3
from numpy import array
from mlp.utils.cs_tools import walk
from talos_rbprm.talos import Robot  # change robot here
multicontact_api.switchToNumpyArray()

ENV_NAME = "multicontact/ground"

fb, v = display_tools.initScene(Robot, ENV_NAME, False)
gui = v.client.gui
sceneName = v.sceneName
cs = ContactSequence(0)

#Create an initial contact phase :
#q_ref = fb.referenceConfig[::] + [0] * 6
q_ref = [       0.0,
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
                0.,
                0.,
                0.,
                0.,
                0.,
                0.,
                0.]
q_ref = fb.referenceConfig + [0]*6
addPhaseFromConfig(fb, cs, q_ref, [fb.rLegId, fb.lLegId])

walk(fb, cs, 0.6, 0.2, [fb.rLegId, fb.lLegId], [-0.02, 0.02])

display_tools.displaySteppingStones(cs, gui, sceneName, fb)

filename = "talos_flatGround.cs"
print("Write contact sequence binary file : ", filename)
cs.saveAsBinary(filename)
