;; LAB-SCALED domain with 4 workstation(s) (auto-generated)
(define (domain lab-scaled-k4)
  (:requirements :strips :action-costs)
  (:predicates (MainPowerOff) (MainPowerOn) (LabUnclean) (LabClean) (NetworkDown) (NetworkUp) (ProjectorOff) (ProjectorOn) (InstructorAbsent) (InstructorPresent) (SoftwareReady) (LabStarted) (PC1Off) (PC1On) (PC1SoftwareInstalled) (PC1Ready) (PC2Off) (PC2On) (PC2SoftwareInstalled) (PC2Ready) (PC3Off) (PC3On) (PC3SoftwareInstalled) (PC3Ready) (PC4Off) (PC4On) (PC4SoftwareInstalled) (PC4Ready))
  (:functions (total-cost))
  (:action CleanLab
    :parameters ()
    :precondition (and (LabUnclean) (MainPowerOff))
    :effect (and (LabClean) (not (LabUnclean)) (increase (total-cost) 15)))
  (:action SwitchOnMainPower
    :parameters ()
    :precondition (and (MainPowerOff))
    :effect (and (MainPowerOn) (not (MainPowerOff)) (increase (total-cost) 1)))
  (:action ConnectNetwork
    :parameters ()
    :precondition (and (MainPowerOn) (NetworkDown))
    :effect (and (NetworkUp) (not (NetworkDown)) (increase (total-cost) 2)))
  (:action PrepareProjector
    :parameters ()
    :precondition (and (ProjectorOff) (MainPowerOn))
    :effect (and (ProjectorOn) (not (ProjectorOff)) (increase (total-cost) 2)))
  (:action SwitchOffProjector
    :parameters ()
    :precondition (and (ProjectorOn))
    :effect (and (ProjectorOff) (not (ProjectorOn)) (increase (total-cost) 1)))
  (:action BootPC1
    :parameters ()
    :precondition (and (PC1Off) (MainPowerOn))
    :effect (and (PC1On) (not (PC1Off)) (increase (total-cost) 1)))
  (:action InstallSoftwarePC1
    :parameters ()
    :precondition (and (PC1On) (NetworkUp))
    :effect (and (PC1SoftwareInstalled) (increase (total-cost) 5)))
  (:action ActivateLicensePC1
    :parameters ()
    :precondition (and (PC1SoftwareInstalled) (NetworkUp))
    :effect (and (PC1Ready) (increase (total-cost) 1)))
  (:action ShutDownPC1
    :parameters ()
    :precondition (and (PC1On))
    :effect (and (PC1Off) (not (PC1On)) (increase (total-cost) 1)))
  (:action BootPC2
    :parameters ()
    :precondition (and (PC2Off) (MainPowerOn))
    :effect (and (PC2On) (not (PC2Off)) (increase (total-cost) 1)))
  (:action InstallSoftwarePC2
    :parameters ()
    :precondition (and (PC2On) (NetworkUp))
    :effect (and (PC2SoftwareInstalled) (increase (total-cost) 5)))
  (:action ActivateLicensePC2
    :parameters ()
    :precondition (and (PC2SoftwareInstalled) (NetworkUp))
    :effect (and (PC2Ready) (increase (total-cost) 1)))
  (:action ShutDownPC2
    :parameters ()
    :precondition (and (PC2On))
    :effect (and (PC2Off) (not (PC2On)) (increase (total-cost) 1)))
  (:action BootPC3
    :parameters ()
    :precondition (and (PC3Off) (MainPowerOn))
    :effect (and (PC3On) (not (PC3Off)) (increase (total-cost) 1)))
  (:action InstallSoftwarePC3
    :parameters ()
    :precondition (and (PC3On) (NetworkUp))
    :effect (and (PC3SoftwareInstalled) (increase (total-cost) 5)))
  (:action ActivateLicensePC3
    :parameters ()
    :precondition (and (PC3SoftwareInstalled) (NetworkUp))
    :effect (and (PC3Ready) (increase (total-cost) 1)))
  (:action ShutDownPC3
    :parameters ()
    :precondition (and (PC3On))
    :effect (and (PC3Off) (not (PC3On)) (increase (total-cost) 1)))
  (:action BootPC4
    :parameters ()
    :precondition (and (PC4Off) (MainPowerOn))
    :effect (and (PC4On) (not (PC4Off)) (increase (total-cost) 1)))
  (:action InstallSoftwarePC4
    :parameters ()
    :precondition (and (PC4On) (NetworkUp))
    :effect (and (PC4SoftwareInstalled) (increase (total-cost) 5)))
  (:action ActivateLicensePC4
    :parameters ()
    :precondition (and (PC4SoftwareInstalled) (NetworkUp))
    :effect (and (PC4Ready) (increase (total-cost) 1)))
  (:action ShutDownPC4
    :parameters ()
    :precondition (and (PC4On))
    :effect (and (PC4Off) (not (PC4On)) (increase (total-cost) 1)))
  (:action VerifyAllWorkstations
    :parameters ()
    :precondition (and (PC1Ready) (PC2Ready) (PC3Ready) (PC4Ready))
    :effect (and (SoftwareReady) (increase (total-cost) 1)))
  (:action CallInstructor
    :parameters ()
    :precondition (and (InstructorAbsent) (LabClean) (SoftwareReady) (ProjectorOn))
    :effect (and (InstructorPresent) (not (InstructorAbsent)) (increase (total-cost) 3)))
  (:action StartLab
    :parameters ()
    :precondition (and (LabClean) (SoftwareReady) (ProjectorOn) (InstructorPresent))
    :effect (and (LabStarted) (increase (total-cost) 1)))
)
