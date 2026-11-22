;; =====================================================================
;; LAB-BASIC : the laboratory set-up domain exactly as stated in the
;; project question (BCS515B, Project 14), written in STRIPS PDDL.
;;
;; Negative conditions such as "projector is off" are modelled as their own
;; facts (ProjectorOff) because STRIPS uses the closed-world assumption and
;; only allows positive preconditions.
;; =====================================================================
(define (domain lab-basic)
  (:requirements :strips)

  (:predicates
    (ProjectorOff) (ProjectorOn)
    (ComputersAvailable)
    (LabUnclean) (LabClean)
    (SoftwareNotInstalled) (SoftwareReady)
    (InstructorAbsent) (InstructorPresent)
    (LabStarted))

  (:action CleanLab
    :parameters ()
    :precondition (and (LabUnclean))
    :effect (and (LabClean) (not (LabUnclean))))

  (:action InstallSoftware
    :parameters ()
    :precondition (and (ComputersAvailable) (SoftwareNotInstalled))
    :effect (and (SoftwareReady) (not (SoftwareNotInstalled))))

  (:action PrepareProjector
    :parameters ()
    :precondition (and (ProjectorOff))
    :effect (and (ProjectorOn) (not (ProjectorOff))))

  ;; The instructor is called only once the room is ready for students.
  (:action CallInstructor
    :parameters ()
    :precondition (and (InstructorAbsent) (LabClean) (SoftwareReady) (ProjectorOn))
    :effect (and (InstructorPresent) (not (InstructorAbsent))))

  (:action StartLab
    :parameters ()
    :precondition (and (ProjectorOn) (LabClean) (SoftwareReady) (InstructorPresent))
    :effect (and (LabStarted)))

  ;; ---- "undo" actions: legal, but they move the lab away from the goal.
  ;; They make arbitrary action sequences fail and keep the search honest.
  (:action SwitchOffProjector
    :parameters ()
    :precondition (and (ProjectorOn))
    :effect (and (ProjectorOff) (not (ProjectorOn))))

  (:action InstructorLeaves
    :parameters ()
    :precondition (and (InstructorPresent))
    :effect (and (InstructorAbsent) (not (InstructorPresent))))
)
