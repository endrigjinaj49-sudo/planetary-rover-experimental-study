(define (problem memory-rover-simple)
  (:domain memory-rover)

  (:objects
    rover1 - rover
    base-station site1 - location
    data1 - data
  )

  (:init
    ;; Initial rover position
    (at rover1 base-station)

    ;; Base station
    (base base-station)

    ;; Map connections
    (connected base-station site1)
    (connected site1 base-station)

    ;; Data location
    (data-at data1 site1)

    ;; Initial memory values
    (= (used-memory rover1) 0)
    (= (memory-capacity rover1) 10)
    (= (data-size data1) 4)
  )

  (:goal
    (and
      (offloaded data1)
    )
  )
)