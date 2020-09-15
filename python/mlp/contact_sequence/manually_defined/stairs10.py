from mlp.utils.cs_tools import addPhaseFromConfig, setFinalState
from pinocchio import SE3
from numpy import array
import multicontact_api
from multicontact_api import ContactSequence
import mlp.viewer.display_tools as display_tools
from talos_rbprm.talos import Robot  # change robot here

multicontact_api.switchToNumpyArray()

ENV_NAME = "multicontact/bauzil_stairs"

fb, v = display_tools.initScene(Robot, ENV_NAME, False)
gui = v.client.gui
sceneName = v.sceneName

cs = ContactSequence(0)

#Create an initial contact phase :
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
        0.
    ] + [0] * 6
q_ref[0:2] = [0.07, 1.2]
#q_ref[2] += 0.001
addPhaseFromConfig(fb, cs, q_ref, [fb.rLegId, fb.lLegId])

num_steps = 6
step_height = 0.1
step_width = 0.3
displacement = SE3.Identity()
displacement.translation = array([step_width, 0, step_height])

for i in range(num_steps):
    cs.moveEffectorOf(fb.rfoot, displacement)
    cs.moveEffectorOf(fb.lfoot, displacement)

q_end = q_ref[::]
q_end[0] += step_width * num_steps
q_end[2] += step_height * num_steps
fb.setCurrentConfig(q_end)
com = fb.getCenterOfMass()
setFinalState(cs, array(com), q=q_end)

display_tools.displaySteppingStones(cs, gui, sceneName, fb)


DEMO_NAME = "talos_stairs10"
filename = DEMO_NAME + ".cs"
print("Write contact sequence binary file : ", filename)
cs.saveAsBinary(filename)
