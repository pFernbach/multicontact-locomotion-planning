from mlp.utils.cs_tools import addPhaseFromConfig
import multicontact_api
from multicontact_api import ContactSequence
import mlp.viewer.display_tools as display_tools
from pinocchio import SE3
from numpy import array
from mlp.utils.cs_tools import walk, setFinalState
from talos_rbprm.talos import Robot  # change robot here
multicontact_api.switchToNumpyArray()

ENV_NAME = "multicontact/ground"

fb, v = display_tools.initScene(Robot, ENV_NAME, False)
gui = v.client.gui
sceneName = v.sceneName
cs = ContactSequence(0)


SS_FORWARD = 1.4
DS_FORWARD = 0.3
SS_DIAGONAL = 1.6
DS_DIAGONAL = 0.8

DURATION_FINAL = 2.
FORWARD_STEP_SIZE = 0.2
DIAGONAL_STEP_SIZE = 0.1 # displacement in each direction, not the norm !

FEET_SEPARATION = 0.01
total_x_dist = 0.
total_y_dist = 0.

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
#q_ref = fb.referenceConfig + [0]*6
addPhaseFromConfig(fb, cs, q_ref, [fb.rLegId, fb.lLegId])
cs.contactPhases[0].timeInitial=0.

# first forward part (5 steps):
walk(fb, cs, FORWARD_STEP_SIZE * 4, FORWARD_STEP_SIZE, [fb.rLegId, fb.lLegId], [-FEET_SEPARATION, FEET_SEPARATION], DS_FORWARD, SS_FORWARD)
total_x_dist += FORWARD_STEP_SIZE * 4
cs.resize(cs.size() - 2)
# second part: 4 steps diagonal for each feet:
transform_diagonal = SE3.Identity()
transform_diagonal.translation = array([DIAGONAL_STEP_SIZE + FORWARD_STEP_SIZE/2., -DIAGONAL_STEP_SIZE, 0])
cs.moveEffectorOf(fb.rfoot, transform_diagonal, DS_DIAGONAL, SS_DIAGONAL + 0.2)
transform_diagonal.translation = array([DIAGONAL_STEP_SIZE, -DIAGONAL_STEP_SIZE, 0])

for i in range(4):
    cs.moveEffectorOf(fb.lfoot, transform_diagonal, DS_DIAGONAL, SS_DIAGONAL)
    cs.moveEffectorOf(fb.rfoot, transform_diagonal, DS_DIAGONAL, SS_DIAGONAL)
    total_y_dist += -DIAGONAL_STEP_SIZE
    total_x_dist += DIAGONAL_STEP_SIZE
cs.moveEffectorOf(fb.lfoot, transform_diagonal, DS_DIAGONAL, SS_DIAGONAL)
total_y_dist += -DIAGONAL_STEP_SIZE
total_x_dist += DIAGONAL_STEP_SIZE

#third part: 5 steps forward
walk(fb, cs, FORWARD_STEP_SIZE * 4, FORWARD_STEP_SIZE, [fb.rLegId, fb.lLegId], [0., 0.], DS_FORWARD, SS_FORWARD)
total_x_dist += FORWARD_STEP_SIZE * 4

# fourth path: diagonal the other way:
# second part: 4 steps diagonal for each feet:
transform_diagonal = SE3.Identity()
transform_diagonal.translation = array([DIAGONAL_STEP_SIZE, DIAGONAL_STEP_SIZE, 0])
for i in range(4):
    cs.moveEffectorOf(fb.lfoot, transform_diagonal, DS_DIAGONAL, SS_DIAGONAL)
    cs.moveEffectorOf(fb.rfoot, transform_diagonal, DS_DIAGONAL, SS_DIAGONAL)
    total_y_dist += DIAGONAL_STEP_SIZE
    total_x_dist += DIAGONAL_STEP_SIZE

# last step have to go back to the reference configuration, so we remove the feet separation offset:
transform_diagonal_R = transform_diagonal.copy()
transform_diagonal_L = transform_diagonal.copy()
translation_R = transform_diagonal_R.translation
translation_L = transform_diagonal_L.translation
translation_L[1] -= FEET_SEPARATION
translation_R[1] += FEET_SEPARATION
transform_diagonal_R.translation = translation_R
transform_diagonal_L.translation = translation_L
cs.moveEffectorOf(fb.lfoot, transform_diagonal_L, DS_DIAGONAL, SS_DIAGONAL)
cs.moveEffectorOf(fb.rfoot, transform_diagonal_R, DS_DIAGONAL, SS_DIAGONAL)
total_y_dist += DIAGONAL_STEP_SIZE
total_x_dist += DIAGONAL_STEP_SIZE

q_end = fb.referenceConfig[::] + [0] * 6
q_end[0] += total_x_dist
q_end[1] += total_y_dist
fb.setCurrentConfig(q_end)
com = fb.getCenterOfMass()
setFinalState(cs, com, q=q_end)
cs.contactPhases[-1].duration = DURATION_FINAL
display_tools.displaySteppingStones(cs, gui, sceneName, fb)

filename = "talos_flatGround.cs"
print("Write contact sequence binary file : ", filename)
cs.saveAsBinary(filename)
