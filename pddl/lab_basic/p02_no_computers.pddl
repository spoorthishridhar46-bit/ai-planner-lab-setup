;; Unsolvable instance: no computers are available, so software can never be
;; installed. A correct planner must report "no plan" instead of returning an
;; arbitrary sequence.
(define (problem p02-no-computers)
  (:domain lab-basic)
  (:init
    (ProjectorOff)
    (LabUnclean)
    (SoftwareNotInstalled)
    (InstructorAbsent))
  (:goal (and
    (ProjectorOn)
    (LabClean)
    (SoftwareReady)
    (InstructorPresent)
    (LabStarted))))
